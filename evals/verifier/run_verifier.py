#!/usr/bin/env python3
"""Run the number verifier on a set of answers and compare with reference grades.

  .venv/bin/python evals/verifier/run_verifier.py baseline evals/baseline/agent_loop/runs/<run>
  .venv/bin/python evals/verifier/run_verifier.py closed-book
  .venv/bin/python evals/verifier/run_verifier.py closed-book evals/contamination/closed_book/runs/selected --out evals/verifier/runs/selected

Extractions are cached in the output folder, so re-running only redoes the
deterministic comparison. Reference grades: the run's judge majority (baseline,
or a closed-book answer folder) or the human grades (default closed-book, the
frozen 15 in batch-1 and batch-2 only).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from number_verifier import extract, grade_check

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import llm  # noqa: E402

OUT = Path(__file__).resolve().parent / "runs"
QUESTIONS = [
    ROOT / "evals" / "contamination" / "questions.csv",
    ROOT / "evals" / "contamination" / "closed_book" / "batch2_questions.csv",
]
CLOSED = ROOT / "evals" / "contamination" / "closed_book" / "runs"
HUMAN = CLOSED / "batch-1" / "grades_human.csv"
COST_CAP = 10.0


def baseline_out(run_dir: Path) -> Path:
    """Default output folder for a baseline run. Agent-loop runs get their own
    prefix, so a run name shared with another output folder never reuses its cache."""
    run_dir = Path(run_dir)
    meta_path = run_dir / "run_meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    if meta.get("harness") == "agent_loop":
        return OUT / f"agent-loop-{run_dir.name}"
    return OUT / run_dir.name


def answer_sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def is_stale(entry: dict | None, answer: str) -> bool:
    """A cached extraction is reused only for the same answer text. Entries saved
    before the hash was recorded carry no hash and are kept."""
    if entry is None:
        return True
    sha = entry.get("_answer_sha")
    return sha is not None and sha != answer_sha(answer)


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def baseline_items(run: Path) -> tuple[dict, list[dict]]:
    items = {}
    for path in sorted((run / "answers").glob("vals-*.json")):
        a = json.loads(path.read_text())
        items[a["id"]] = {
            "question": a["question"],
            "gold": a["answer"],
            "answer": a["model_answer"],
        }
    # After apply_policy, judge_grades_majority.csv holds the merged grades; the
    # judge's own majority is kept in the _judge backup.
    for name in ("judge_grades_majority_judge.csv", "judge_grades_majority.csv"):
        path = run / "judge" / name
        if path.exists():
            return items, read_csv(path)
    sys.exit(f"no judge majority grades for {run}")


def vals_gold() -> dict[str, dict]:
    rows = list(read_csv(ROOT / "data" / "vals" / "public.csv"))
    return {f"vals-{i:02d}": r for i, r in enumerate(rows, start=1)}


def _answer_text(payload: dict) -> str:
    response = payload["response"]
    if isinstance(response, str):
        response = json.loads(response)
    return llm.response_text(response)


def closed_book_items(run: Path | None = None) -> tuple[dict, list[dict]]:
    gold = vals_gold()
    if run is None:
        answer_paths = [
            *sorted((CLOSED / "batch-1").glob("vals-*.json")),
            *sorted((CLOSED / "batch-2").glob("vals-*.json")),
        ]
        reference = [r for r in read_csv(HUMAN) if r["result"]]
    else:
        answer_paths = sorted(run.glob("vals-*.json"))
        candidates = [
            run / "judge" / "judge_grades_majority.csv",
            run / "judge_grades_majority.csv",
            ROOT
            / "evals"
            / "contamination"
            / "closed_book"
            / "judge"
            / "runs"
            / run.name
            / "judge_grades_majority.csv",
        ]
        judge_path = next((p for p in candidates if p.exists()), None)
        if judge_path is None:
            sys.exit(f"no judge majority grades for {run}")
        reference = read_csv(judge_path)
    items = {}
    for path in answer_paths:
        a = json.loads(path.read_text())
        qid = a["question_id"]
        items[qid] = {
            "question": a["question"],
            "gold": gold[qid]["Answer"],
            "answer": _answer_text(a),
        }
    return items, [r for r in reference if r["question_id"] in items and r["result"]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", choices=["baseline", "closed-book"])
    ap.add_argument(
        "run",
        nargs="?",
        type=Path,
        help="run folder (required for baseline; optional closed-book answer dir)",
    )
    ap.add_argument(
        "--out", type=Path, help="output folder (reuses its cached extractions)"
    )
    ap.add_argument(
        "--exclude", nargs="*", default=[], help="question ids left out of the stats"
    )
    ap.add_argument(
        "--model", help="extraction model (default: the verifier model in agent/llm.py)"
    )
    args = ap.parse_args()

    if args.source == "baseline":
        if not args.run:
            sys.exit("baseline requires a run folder")
        items, reference = baseline_items(args.run)
        default_out = baseline_out(args.run)
    else:
        items, reference = closed_book_items(args.run)
        default_out = OUT / (args.run.name if args.run else "closed-book")
    out = args.out or default_out
    out.mkdir(parents=True, exist_ok=True)
    cache_path = out / "extractions.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}

    checks: dict[str, list[dict]] = {}
    for r in reference:
        checks.setdefault(r["question_id"], []).append(
            {
                "check_id": int(r["check_id"]),
                "operator": r["operator"],
                "criteria": r["criteria"],
            }
        )

    ap_model = args.model or llm.VERIFIER_MODEL
    todo = [q for q in checks if is_stale(cache.get(q), items[q]["answer"])]
    spent = sum(c.get("_cost", 0) for c in cache.values())

    def run_one(qid: str):
        it = items[qid]
        found, cost = extract(
            it["question"], it["gold"], checks[qid], it["answer"], model=ap_model
        )
        return qid, {
            "_cost": cost,
            "_answer_sha": answer_sha(it["answer"]),
            **{str(k): v for k, v in found.items()},
        }

    with ThreadPoolExecutor(8) as pool:
        for qid, data in pool.map(run_one, todo):
            cache[qid] = data
            spent += data["_cost"]
            cache_path.write_text(json.dumps(cache, indent=1, ensure_ascii=False))
            if spent > COST_CAP:
                raise SystemExit(f"cost cap reached at ${spent:.2f}")

    rows = []
    for r in reference:
        ext = cache[r["question_id"]].get(str(r["check_id"]), {})
        verdict, details = grade_check(r["operator"], ext.get("quantities") or [])
        rows.append(
            {
                "question_id": r["question_id"],
                "check_id": r["check_id"],
                "operator": r["operator"],
                "criteria": r["criteria"],
                "verifier": verdict,
                "reference": r["result"],
                "non_numeric_claim": ext.get("non_numeric_claim", False),
                "details": json.dumps(
                    [
                        {k: d.get(k) for k in ("gold", "answer", "ok", "why")}
                        for d in details
                    ],
                    ensure_ascii=False,
                ),
            }
        )
    with (out / "verdicts.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    excluded = set(args.exclude)
    scored = [r for r in rows if r["question_id"] not in excluded]
    decided = [r for r in scored if r["verifier"] not in ("not numeric", "not found")]
    agree = sum(r["verifier"] == r["reference"] for r in decided)
    counts = Counter(r["verifier"] for r in scored)
    print(
        f"checks {len(scored)} (excluded {sorted(excluded) or 'none'}): {dict(counts)}"
    )
    print(
        f"decided numeric checks {len(decided)}: agree {agree}, disagree {len(decided) - agree}; "
        f"extraction cost ${spent:.2f}"
    )
    for r in rows:
        if (
            r["verifier"] not in ("not numeric", "not found")
            and r["verifier"] != r["reference"]
        ):
            tag = " [excluded]" if r["question_id"] in excluded else ""
            print(
                f"  {r['question_id']} #{r['check_id']}{tag} verifier={r['verifier']} reference={r['reference']}"
                f"{' (non-numeric claim too)' if r['non_numeric_claim'] else ''}: {r['details']}"
            )


if __name__ == "__main__":
    main()
