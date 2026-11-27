"""Offline regrade: re-run the deterministic number verifier on cached extractions and merge it
with the saved judge majority, without any API call and without writing into the run folders.

  .venv/bin/python -m evals.stability.regrade RUN [RUN ...] [--json OUT]

For each run: the saved overall label (results.csv) against the label the current verifier and
policy would give. Questions whose answer has no cached extraction (or a stale one) keep their
saved label and are listed as "no extraction".
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "evals" / "verifier"
if str(VERIFIER) not in sys.path:
    sys.path.insert(0, str(VERIFIER))

from apply_policy import overall_from_checks
from number_verifier import grade_check
from run_verifier import answer_sha, baseline_out

RUNS = ROOT / "evals" / "baseline" / "agent_loop" / "runs"


def _csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def merge(judge_checks: list[dict], extraction: dict, answer: str) -> str:
    """Overall label from the judge's checks with decided numeric correctness checks replaced
    by the verifier (the agreed policy in apply_policy)."""
    merged = []
    for r in judge_checks:
        row = dict(r)
        if r["operator"] == "correctness":
            ext = extraction.get(str(r["check_id"]), {})
            verdict, _ = grade_check(r["operator"], ext.get("quantities") or [], text=answer, label=r["criteria"])
            if verdict in {"met", "not met"}:
                row["result"] = verdict
        merged.append(row)
    return overall_from_checks(merged, judge_checks[0]["overall"])


def regrade(run_dir: Path) -> dict:
    jdir = run_dir / "judge"
    judge_path = next((p for p in (jdir / "judge_grades_majority_judge.csv", jdir / "judge_grades_majority.csv") if p.exists()), None)
    if judge_path is None or not (run_dir / "results.csv").exists():
        return {"run": run_dir.name, "skipped": "not judged"}
    cache_path = baseline_out(run_dir) / "extractions.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    by_q: dict[str, list[dict]] = defaultdict(list)
    for r in _csv(judge_path):
        by_q[r["question_id"]].append(r)
    saved = {r["id"]: r["overall"] for r in _csv(run_dir / "results.csv")}
    changes, missing, new = [], [], {}
    for qid, old in saved.items():
        path = run_dir / "answers" / f"{qid}.json"
        answer = json.loads(path.read_text()).get("model_answer", "") if path.exists() else ""
        ext = cache.get(qid)
        if qid not in by_q or ext is None or (ext.get("_answer_sha") not in (None, answer_sha(answer))):
            new[qid] = old
            if qid in by_q:
                missing.append(qid)
            continue
        new[qid] = merge(by_q[qid], ext, answer)
        if new[qid] != old:
            changes.append({"id": qid, "saved": old, "regraded": new[qid]})
    return {"run": run_dir.name, "saved_right": sum(v == "right" for v in saved.values()),
            "regraded_right": sum(v == "right" for v in new.values()), "changes": changes,
            "no_extraction": missing, "labels": new}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    out = []
    for name in args.runs:
        r = regrade(Path(name) if Path(name).is_dir() else RUNS / name)
        out.append(r)
        if "skipped" in r:
            print(f"{r['run']}: skipped ({r['skipped']})")
            continue
        ch = " ".join(f"{c['id']}:{c['saved'][0]}->{c['regraded'][0]}" for c in r["changes"]) or "-"
        print(f"{r['run']}: {r['saved_right']} -> {r['regraded_right']}  {ch}"
              + (f"  (no extraction: {' '.join(r['no_extraction'])})" if r["no_extraction"] else ""))
    if args.json:
        args.json.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
