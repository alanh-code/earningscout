"""Shared helpers for baseline runs: question loading, exclusions, run folders, record files, judge CSVs."""

from __future__ import annotations

import csv
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.protocol import SEED

VALS = ROOT / "data" / "vals" / "public.csv"
EXCLUSIONS_PATH = ROOT / "evals" / "baseline" / "excluded_questions.csv"
JUDGE_PASSES = 3
N_PUBLIC = 50


def load_questions() -> list[dict]:
    with VALS.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    items = []
    for i, row in enumerate(rows, start=1):
        rubric = json.loads(row["Rubric"])
        if not isinstance(rubric, list):
            sys.exit(f"vals-{i:02d}: rubric is not a JSON list")
        items.append(
            {
                "id": f"vals-{i:02d}",
                "type": row["Question Type"],
                "question": row["Question"],
                "answer": row["Answer"],
                "rubric": rubric,
            }
        )
    if len(items) != N_PUBLIC:
        sys.exit(f"expected {N_PUBLIC} public questions, got {len(items)}")
    return items


def majority_grade(jr, parses: list[dict], rubric: list) -> dict:
    overalls = [p["overall"] for p in parses]
    overall, tie = jr.majority_label(overalls)
    checks = {}
    for i, check in enumerate(rubric, start=1):
        votes = []
        for p in parses:
            row = p["checks"][i - 1]
            votes.append(row["result"])
        result, _ = jr.majority_label(votes)
        checks[i] = {
            "operator": check["operator"],
            "criteria": check["criteria"],
            "result": result,
        }
    reasons = [p.get("reason") or "" for p in parses if p.get("overall") == overall]
    return {
        "overall": overall,
        "tie": tie,
        "reason": reasons[0] if reasons else parses[0].get("reason") or "",
        "checks": checks,
        "run_overalls": overalls,
    }


def load_exclusions(path: Path = EXCLUSIONS_PATH) -> dict[str, str]:
    """Map excluded question ids to a one-line reason. Missing file means none excluded."""
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            qid = (row.get("id") or "").strip()
            if qid:
                out[qid] = (row.get("reason") or "").strip()
    return out


def run_folder_name(raw: str | None) -> str:
    """A single role name, not a timestamp and not a path."""
    name = (raw or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
        sys.exit(
            "--name must be a single folder name (letters, numbers, dot, underscore, dash)"
        )
    if re.fullmatch(r"\d{8}-\d{6}", name):
        sys.exit("--name cannot be a timestamp")
    return name


def bootstrap_ci(
    labels: list[str], n_boot: int = 10000, seed: int = SEED
) -> tuple[float, float, float]:
    n = len(labels)
    acc = sum(x == "right" for x in labels) / n if n else 0.0
    rng = random.Random(seed)  # nosec B311
    accs = []
    for _ in range(n_boot):
        sample = [labels[rng.randrange(n)] for _ in range(n)]
        accs.append(sum(x == "right" for x in sample) / n)
    accs.sort()
    lo = accs[int(0.025 * n_boot)]
    hi = accs[min(n_boot - 1, int(0.975 * n_boot))]
    return acc, lo, hi


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )


def save_agent_record(run_dir: Path, rec: dict) -> None:
    slim = {k: v for k, v in rec.items() if k != "turns"}
    write_json(run_dir / "answers" / f"{rec['id']}.json", slim)
    raw_path = run_dir / "raw" / f"{rec['id']}.json"
    if rec.get("turns"):
        write_json(raw_path, rec)
        write_json(
            run_dir / "traces" / f"{rec['id']}.json",
            {
                "id": rec["id"],
                "n_turns": rec.get("n_turns"),
                "n_tool_calls": rec.get("n_tool_calls"),
                "tool_calls": rec.get("tool_calls"),
                "turns": rec["turns"],
            },
        )
    elif not raw_path.exists():
        write_json(raw_path, rec)


def write_judge_outputs(
    run_dir: Path, records: list[dict], pass_parses: list[dict], jr
) -> None:
    for pass_i in range(JUDGE_PASSES):
        rows = []
        for rec in records:
            parsed = pass_parses[pass_i][rec["id"]]
            for i, check in enumerate(rec["rubric"], start=1):
                got = parsed["checks"][i - 1]
                rows.append(
                    {
                        "question_id": rec["id"],
                        "check_id": i,
                        "operator": check["operator"],
                        "criteria": check["criteria"],
                        "result": got["result"],
                        "overall": parsed["overall"],
                        "reason": parsed.get("reason") or "",
                    }
                )
        with (run_dir / "judge" / f"judge_grades_run{pass_i + 1}.csv").open(
            "w", newline="", encoding="utf-8"
        ) as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "question_id",
                    "check_id",
                    "operator",
                    "criteria",
                    "result",
                    "overall",
                    "reason",
                ],
            )
            w.writeheader()
            w.writerows(rows)

    maj_rows = []
    for rec in records:
        parses = [pass_parses[i][rec["id"]] for i in range(JUDGE_PASSES)]
        maj = majority_grade(jr, parses, rec["rubric"])
        rec["overall"] = maj["overall"]
        rec["judge_reason"] = maj["reason"]
        rec["judge_run_overalls"] = maj["run_overalls"]
        save_agent_record(run_dir, rec)
        for i, check in enumerate(rec["rubric"], start=1):
            got = maj["checks"][i]
            maj_rows.append(
                {
                    "question_id": rec["id"],
                    "check_id": i,
                    "operator": check["operator"],
                    "criteria": check["criteria"],
                    "result": got["result"],
                    "overall": maj["overall"],
                    "reason": maj["reason"],
                }
            )
    (run_dir / "judge").mkdir(exist_ok=True)
    with (run_dir / "judge" / "judge_grades_majority.csv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "question_id",
                "check_id",
                "operator",
                "criteria",
                "result",
                "overall",
                "reason",
            ],
        )
        w.writeheader()
        w.writerows(maj_rows)

    with (run_dir / "results.csv").open("w", newline="", encoding="utf-8") as f:
        fields = [
            "id",
            "type",
            "overall",
            "cost_usd",
            "latency_s",
            "n_tool_calls",
            "stop_reason",
            "judge_reason",
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in records:
            w.writerow({k: r.get(k) for k in fields})
