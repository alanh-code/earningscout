#!/usr/bin/env python3
"""Apply verifier/judge precedence to a baseline run and rewrite the scored summary.

Agreed policy: on a decided numeric correctness check (verifier is met or
not met), the verifier wins; on contradiction checks and on non-numeric / not-found
verifier verdicts, the judge majority wins.

The judge's own grades are kept as judge/judge_grades_majority_judge.csv and
results_judge.csv.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def backup_path(folder: Path, stem: str) -> Path:
    """The pre-policy copy of a judge file."""
    return folder / f"{stem}_judge.csv"


def overall_from_checks(checks: list[dict], prev: str) -> str:
    if prev == "abstain":
        return "abstain"
    correct = [c for c in checks if c["operator"] == "correctness"]
    contra = [c for c in checks if c["operator"] == "contradiction"]
    all_met = all(c["result"] == "met" for c in correct)
    no_contra = all(c["result"] != "triggered" for c in contra)
    return "right" if all_met and no_contra else "wrong"


def apply(run_dir: Path, verdicts_path: Path) -> dict:
    majority_path = run_dir / "judge" / "judge_grades_majority.csv"
    majority_bak = backup_path(run_dir / "judge", "judge_grades_majority")
    if not majority_bak.exists():
        majority_bak.write_bytes(majority_path.read_bytes())
    judge = read_csv(majority_bak)
    verdicts = {
        (r["question_id"], int(r["check_id"])): r for r in read_csv(verdicts_path)
    }

    by_q: dict[str, list[dict]] = defaultdict(list)
    for r in judge:
        by_q[r["question_id"]].append(r)

    merged_rows = []
    check_changes = []
    overall_changes = []
    for qid, checks in by_q.items():
        new_checks = []
        for r in checks:
            cid = int(r["check_id"])
            v = verdicts.get((qid, cid), {})
            ver = v.get("verifier") or ""
            judge_res = r["result"]
            use = judge_res
            source = "judge"
            if r["operator"] == "correctness" and ver in {"met", "not met"}:
                use = ver
                source = "verifier"
            row = dict(r)
            row["result"] = use
            row["source"] = source
            row["judge_result"] = judge_res
            row["verifier"] = ver
            new_checks.append(row)
            if use != judge_res:
                check_changes.append(
                    {
                        "id": qid,
                        "check_id": cid,
                        "operator": r["operator"],
                        "judge": judge_res,
                        "final": use,
                        "source": source,
                        "criteria": r["criteria"][:160],
                    }
                )
        prev_overall = checks[0]["overall"]
        new_overall = overall_from_checks(new_checks, prev_overall)
        reason = checks[0].get("reason") or ""
        if new_overall != prev_overall:
            reason = (
                f"Merged with number verifier: overall {prev_overall} -> {new_overall}. "
                + reason
            )
            overall_changes.append(
                {"id": qid, "judge": prev_overall, "final": new_overall}
            )
        for row in new_checks:
            row["overall"] = new_overall
            row["reason"] = reason
            merged_rows.append(row)

    fields = [
        "question_id",
        "check_id",
        "operator",
        "criteria",
        "result",
        "overall",
        "reason",
        "source",
        "judge_result",
        "verifier",
    ]
    write_csv(
        run_dir / "judge" / "judge_grades_majority_merged.csv", merged_rows, fields
    )
    # Official scored majority after policy.
    write_csv(
        run_dir / "judge" / "judge_grades_majority.csv",
        [
            {
                k: r[k]
                for k in [
                    "question_id",
                    "check_id",
                    "operator",
                    "criteria",
                    "result",
                    "overall",
                    "reason",
                ]
            }
            for r in merged_rows
        ],
        [
            "question_id",
            "check_id",
            "operator",
            "criteria",
            "result",
            "overall",
            "reason",
        ],
    )

    results_path = run_dir / "results.csv"
    results_bak = backup_path(run_dir, "results")
    if not results_bak.exists():
        results_bak.write_bytes(results_path.read_bytes())
    results = read_csv(results_bak)
    new_overall = {r["question_id"]: r["overall"] for r in merged_rows}
    new_reason = {r["question_id"]: r["reason"] for r in merged_rows}
    for r in results:
        r["judge_overall"] = r["overall"]
        r["overall"] = new_overall.get(r["id"], r["overall"])
        r["judge_reason"] = new_reason.get(r["id"], r.get("judge_reason") or "")
    write_csv(results_path, results, list(results[0].keys()))

    # Refresh summary.md from the (now merged) results.
    spec = importlib.util.spec_from_file_location(
        "agent_loop_run", ROOT / "evals" / "baseline" / "agent_loop" / "run.py"
    )
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    runner.rewrite_summary(run_dir)

    report = {
        "check_changes": check_changes,
        "overall_changes": overall_changes,
        "n_check_changes": len(check_changes),
        "n_overall_changes": len(overall_changes),
    }
    (run_dir / "verifier_policy.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )
    print(
        f"{len(check_changes)} check-level changes, {len(overall_changes)} overall flips"
    )
    for c in overall_changes:
        print(f"  {c['id']} {c['judge']} -> {c['final']}")
    for c in check_changes:
        print(
            f"  {c['id']} #{c['check_id']} {c['operator']} judge={c['judge']} final={c['final']}"
        )
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument(
        "--verdicts",
        type=Path,
        help="default: the run's verifier folder (run_verifier.baseline_out)/verdicts.csv",
    )
    args = ap.parse_args()
    run_dir = args.run_dir
    sys.path.insert(0, str(ROOT / "evals" / "verifier"))
    from run_verifier import baseline_out

    verdicts = args.verdicts or (baseline_out(run_dir) / "verdicts.csv")
    if not verdicts.exists():
        sys.exit(f"missing verdicts: {verdicts}")
    apply(run_dir, verdicts)


if __name__ == "__main__":
    main()
