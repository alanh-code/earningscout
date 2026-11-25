"""Regression gate: freeze the scored baseline runs, then check candidate runs against them.

  freeze              read the baseline runs, write baseline_freeze.json
  check RUN [RUN...]  compare candidate runs with the frozen baseline, write gate_report.{md,json}

Accuracy rule. Under the null hypothesis that a candidate agent is unchanged, question q is
right with its baseline frequency p_q (right runs / baseline runs), independently across
questions. The expected right count is sum(p_q) with variance sum(p_q * (1 - p_q)); for the
mean of k candidate runs the variance is divided by k. The gate fails when the candidate mean
right count is more than ACCURACY_Z standard deviations below that expectation (one-sided,
about a 2% false-alarm rate when nothing changed). It warns when the mean falls below the
worst baseline run, and when any always-right question (right in every baseline run) is wrong.

Scoring uses the questions in each run's results.csv minus those listed in
evals/baseline/excluded_questions.csv.

Hard failures also cover leak-scan hits, question sets that differ from the frozen set, and
missing judge, verifier, policy or leak-scan artifacts.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RUNS = ROOT / "evals" / "baseline" / "agent_loop" / "runs"
VERIFIER_RUNS = ROOT / "evals" / "verifier" / "runs"
FREEZE_PATH = HERE / "baseline_freeze.json"
BASELINE_RUNS = ("official", "repeat_2", "repeat_3")
ACCURACY_Z = 2.0


def _load_common():
    spec = importlib.util.spec_from_file_location(
        "baseline_common", ROOT / "evals" / "baseline" / "common.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


common = _load_common()
UNDECIDED = ("not numeric", "not found")
JUDGE_FILES = (
    "judge_grades_majority.csv",
    "judge_grades_run1.csv",
    "judge_grades_run2.csv",
    "judge_grades_run3.csv",
)


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def verifier_dir(run_dir: Path, verifier_root: Path = VERIFIER_RUNS) -> Path:
    return verifier_root / f"agent-loop-{run_dir.name}"


def missing_artifacts(run_dir: Path, verifier_root: Path = VERIFIER_RUNS) -> list[str]:
    needed = [
        run_dir / "results.csv",
        run_dir / "run_meta.json",
        run_dir / "leak_scan.json",
        run_dir / "verifier_policy.json",
        verifier_dir(run_dir, verifier_root) / "verdicts.csv",
        *(run_dir / "judge" / name for name in JUDGE_FILES),
    ]
    return [str(p.relative_to(p.parents[2])) for p in needed if not p.exists()]


def verifier_agreement(run_dir: Path, ids: set[str], verifier_root: Path) -> dict:
    rows = read_csv(verifier_dir(run_dir, verifier_root) / "verdicts.csv")
    decided = [
        r for r in rows if r["question_id"] in ids and r["verifier"] not in UNDECIDED
    ]
    agree = sum(r["verifier"] == r["reference"] for r in decided)
    return {"agree": agree, "decided": len(decided)}


def load_run(
    run_dir: Path, verifier_root: Path = VERIFIER_RUNS, exclusions=None
) -> dict:
    """Per-question outcomes and run-level stats on the scored questions (exclusions removed)."""
    if exclusions is None:
        exclusions = common.load_exclusions()
    results = [
        r for r in read_csv(run_dir / "results.csv") if r["id"] not in exclusions
    ]
    meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
    leak = json.loads((run_dir / "leak_scan.json").read_text(encoding="utf-8"))
    policy = json.loads((run_dir / "verifier_policy.json").read_text(encoding="utf-8"))
    turns = []
    for r in results:
        answer = run_dir / "answers" / f"{r['id']}.json"
        if answer.exists():
            turns.append(
                json.loads(answer.read_text(encoding="utf-8")).get("n_turns") or 0
            )
    ids = {r["id"] for r in results}
    counts = Counter(r["id"] for r in results)
    duplicates = sorted(q for q, c in counts.items() if c > 1)
    return {
        "name": run_dir.name,
        "duplicate_ids": duplicates,
        "outcomes": {r["id"]: r["overall"] for r in results},
        "types": {r["id"]: r["type"] for r in results},
        "right": sum(r["overall"] == "right" for r in results),
        "n": len(results),
        "cost_usd": float(meta.get("total_cost_usd") or 0),
        "mean_tool_calls": statistics.mean(
            float(r["n_tool_calls"] or 0) for r in results
        )
        if results
        else 0.0,
        "mean_turns": statistics.mean(turns) if turns else 0.0,
        "leak_hits": int(leak.get("n_hits") or 0),
        "verifier": verifier_agreement(run_dir, ids, verifier_root),
        "policy_check_changes": int(policy.get("n_check_changes") or 0),
        "policy_overall_changes": int(policy.get("n_overall_changes") or 0),
    }


def type_accuracy(runs: list[dict]) -> dict[str, dict]:
    tally: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for run in runs:
        for qid, outcome in run["outcomes"].items():
            t = tally[run["types"][qid]]
            t[0] += outcome == "right"
            t[1] += 1
    return {
        k: {"right": r, "total": n, "accuracy": round(r / n, 4)}
        for k, (r, n) in sorted(tally.items())
    }


def build_freeze(runs: list[dict]) -> dict:
    """Deterministic snapshot of the baseline runs."""
    ids = sorted(runs[0]["outcomes"])
    for run in runs:
        if run["duplicate_ids"]:
            raise ValueError(f"run {run['name']} repeats {run['duplicate_ids']}")
    for run in runs[1:]:
        if sorted(run["outcomes"]) != ids:
            raise ValueError(f"run {run['name']} scores a different question set")
    passes = {q: sum(run["outcomes"][q] == "right" for run in runs) for q in ids}
    k = len(runs)
    acc = [run["right"] / run["n"] for run in runs]
    agree = sum(run["verifier"]["agree"] for run in runs)
    decided = sum(run["verifier"]["decided"] for run in runs)
    return {
        "runs": [run["name"] for run in runs],
        "n_runs": k,
        "question_ids": ids,
        "types": {q: runs[0]["types"][q] for q in ids},
        "pass_counts": passes,
        "always_right": [q for q in ids if passes[q] == k],
        "flaky": [q for q in ids if 0 < passes[q] < k],
        "always_wrong": [q for q in ids if passes[q] == 0],
        "per_run": {
            run["name"]: {
                "right": run["right"],
                "n": run["n"],
                "accuracy": round(run["right"] / run["n"], 4),
                "cost_usd": round(run["cost_usd"], 4),
                "mean_tool_calls": round(run["mean_tool_calls"], 3),
                "mean_turns": round(run["mean_turns"], 3),
                "leak_hits": run["leak_hits"],
                "verifier_agree": run["verifier"]["agree"],
                "verifier_decided": run["verifier"]["decided"],
                "policy_check_changes": run["policy_check_changes"],
                "policy_overall_changes": run["policy_overall_changes"],
            }
            for run in runs
        },
        "summary": {
            "mean_accuracy": round(statistics.mean(acc), 4),
            "sd_accuracy": round(statistics.stdev(acc), 4) if k > 1 else 0.0,
            "min_right": min(run["right"] for run in runs),
            "mean_right": round(statistics.mean(run["right"] for run in runs), 4),
            "per_type": type_accuracy(runs),
            "verifier_agreement": round(agree / decided, 4) if decided else None,
            "verifier_agree": agree,
            "verifier_decided": decided,
            "mean_cost_usd": round(statistics.mean(run["cost_usd"] for run in runs), 4),
            "mean_tool_calls": round(
                statistics.mean(run["mean_tool_calls"] for run in runs), 3
            ),
            "mean_turns": round(statistics.mean(run["mean_turns"] for run in runs), 3),
            "leak_hits": sum(run["leak_hits"] for run in runs),
        },
    }


def null_model(freeze: dict, k_runs: int) -> dict:
    p = [c / freeze["n_runs"] for c in freeze["pass_counts"].values()]
    expected = sum(p)
    sd = math.sqrt(sum(x * (1 - x) for x in p) / k_runs)
    return {
        "expected_right": round(expected, 4),
        "sd_right": round(sd, 4),
        "floor_right": round(expected - ACCURACY_Z * sd, 4),
    }


def check(
    run_dirs: list[Path],
    freeze: dict,
    verifier_root: Path = VERIFIER_RUNS,
    exclusions=None,
) -> dict:
    """Gate verdict, failures, warnings and diagnostics for one or more candidate runs."""
    failures: list[str] = []
    warnings: list[str] = []
    frozen = set(freeze["question_ids"])
    runs = []
    for run_dir in run_dirs:
        missing = missing_artifacts(run_dir, verifier_root)
        if missing:
            failures.append(f"{run_dir.name}: missing artifacts: {', '.join(missing)}")
            continue
        run = load_run(run_dir, verifier_root, exclusions)
        if run["duplicate_ids"]:
            failures.append(
                f"{run_dir.name}: repeated question rows {run['duplicate_ids']}"
            )
            continue
        got = set(run["outcomes"])
        if got != frozen:
            failures.append(
                f"{run_dir.name}: question set differs from the frozen {len(frozen)}; "
                f"missing {sorted(frozen - got)}, extra {sorted(got - frozen)}"
            )
            continue
        if run["leak_hits"] > 0:
            failures.append(
                f"{run_dir.name}: leak scan found {run['leak_hits']} gold-source hits"
            )
        runs.append(run)
    report: dict = {
        "candidates": [d.name for d in run_dirs],
        "failures": failures,
        "warnings": warnings,
    }
    if len(runs) != len(run_dirs):
        report["passed"] = False
        return report

    k = len(runs)
    model = null_model(freeze, k)
    mean_right = statistics.mean(run["right"] for run in runs)
    n = len(frozen)
    base = freeze["summary"]
    if mean_right < model["floor_right"]:
        failures.append(
            f"accuracy: mean right {mean_right:.2f}/{n} is below the floor {model['floor_right']:.2f} "
            f"(expected {model['expected_right']:.2f} - {ACCURACY_Z:g} sd {model['sd_right']:.2f})"
        )
    elif mean_right < base["min_right"]:
        warnings.append(
            f"accuracy: mean right {mean_right:.2f}/{n} is below the worst baseline run ({base['min_right']}/{n})"
        )

    per_question = {}
    for q in freeze["question_ids"]:
        cand = sum(run["outcomes"][q] == "right" for run in runs)
        per_question[q] = {
            "baseline": freeze["pass_counts"][q],
            "candidate": cand,
            "candidate_runs": k,
        }
    always_right_regressions = [
        q for q in freeze["always_right"] if per_question[q]["candidate"] < k
    ]
    always_wrong_fixes = [
        q for q in freeze["always_wrong"] if per_question[q]["candidate"] > 0
    ]
    flaky = {q: per_question[q] for q in freeze["flaky"]}
    if always_right_regressions:
        warnings.append(
            "always-right regressions (right in every baseline run, wrong here): "
            + ", ".join(always_right_regressions)
        )

    cand_types = type_accuracy(runs)
    per_type = {
        t: {
            "baseline": base["per_type"][t]["accuracy"],
            "candidate": cand_types[t]["accuracy"],
            "delta_pp": round(
                100 * (cand_types[t]["accuracy"] - base["per_type"][t]["accuracy"]), 1
            ),
            "candidate_right": cand_types[t]["right"],
            "candidate_total": cand_types[t]["total"],
        }
        for t in sorted(base["per_type"])
    }
    agree = sum(run["verifier"]["agree"] for run in runs)
    decided = sum(run["verifier"]["decided"] for run in runs)

    def mean(key: str) -> float:
        return statistics.mean(run[key] for run in runs)

    report.update(
        passed=not failures,
        accuracy={
            "per_run": {run["name"]: f"{run['right']}/{n}" for run in runs},
            "mean_right": round(mean_right, 4),
            "mean_accuracy": round(mean_right / n, 4),
            "baseline_mean_accuracy": base["mean_accuracy"],
            "delta_pp": round(100 * (mean_right / n - base["mean_accuracy"]), 1),
            **model,
        },
        paired={
            "always_right_regressions": always_right_regressions,
            "always_wrong_fixes": always_wrong_fixes,
            "flaky": flaky,
            "gained": [
                q
                for q, v in per_question.items()
                if v["candidate"] / k > v["baseline"] / freeze["n_runs"]
            ],
            "lost": [
                q
                for q, v in per_question.items()
                if v["candidate"] / k < v["baseline"] / freeze["n_runs"]
            ],
        },
        per_type=per_type,
        verifier={
            "agree": agree,
            "decided": decided,
            "agreement": round(agree / decided, 4) if decided else None,
            "baseline_agreement": base["verifier_agreement"],
            "policy_check_changes": sum(run["policy_check_changes"] for run in runs),
            "policy_overall_changes": sum(
                run["policy_overall_changes"] for run in runs
            ),
        },
        usage={
            "mean_cost_usd": round(mean("cost_usd"), 4),
            "baseline_mean_cost_usd": base["mean_cost_usd"],
            "mean_tool_calls": round(mean("mean_tool_calls"), 3),
            "baseline_mean_tool_calls": base["mean_tool_calls"],
            "mean_turns": round(mean("mean_turns"), 3),
            "baseline_mean_turns": base["mean_turns"],
        },
        leak_hits=sum(run["leak_hits"] for run in runs),
    )
    return report


def render(report: dict) -> str:
    verdict = "PASS" if report["passed"] else "FAIL"
    lines = [
        f"# Regression gate: {verdict}",
        "",
        f"Candidates: {', '.join(report['candidates'])}.",
        "",
    ]
    for title, items in (
        ("Failures", report["failures"]),
        ("Warnings", report["warnings"]),
    ):
        lines += [f"## {title}", ""] + ([f"* {x}" for x in items] or ["None."]) + [""]
    if "accuracy" not in report:
        return "\n".join(lines)
    a, v, u, p = (
        report["accuracy"],
        report["verifier"],
        report["usage"],
        report["paired"],
    )
    lines += [
        "## Accuracy",
        "",
        (
            f"Per run: {', '.join(f'{k} {x}' for k, x in a['per_run'].items())}. "
            f"Mean {100 * a['mean_accuracy']:.1f}% vs baseline {100 * a['baseline_mean_accuracy']:.1f}% "
            f"({a['delta_pp']:+.1f} pts)."
        ),
        f"Null model: expected {a['expected_right']:.2f} right, sd {a['sd_right']:.2f}, floor {a['floor_right']:.2f}.",
        "",
        "## Paired comparison",
        "",
        f"* Always-right regressions: {', '.join(p['always_right_regressions']) or 'none'}",
        f"* Always-wrong fixes: {', '.join(p['always_wrong_fixes']) or 'none'}",
        f"* Gained vs baseline rate: {', '.join(p['gained']) or 'none'}",
        f"* Lost vs baseline rate: {', '.join(p['lost']) or 'none'}",
        "* Flaky questions (baseline right runs -> candidate right runs): "
        + (
            ", ".join(
                f"{q} {x['baseline']}/3->{x['candidate']}/{x['candidate_runs']}"
                for q, x in p["flaky"].items()
            )
            or "none"
        ),
        "",
        "## By question type",
        "",
        "| Type | Baseline | Candidate | Delta |",
        "|---|---:|---:|---:|",
        *[
            f"| {t} | {100 * x['baseline']:.0f}% | {x['candidate_right']}/{x['candidate_total']} ({100 * x['candidate']:.0f}%) | {x['delta_pp']:+.1f} |"
            for t, x in report["per_type"].items()
        ],
        "",
        "## Verifier, cost and usage",
        "",
        (
            f"* Verifier and judge agree on {v['agree']}/{v['decided']} decided checks "
            f"({100 * (v['agreement'] or 0):.1f}%; baseline {100 * (v['baseline_agreement'] or 0):.1f}%). "
            f"Policy changed {v['policy_check_changes']} checks and {v['policy_overall_changes']} overall labels."
        ),
        (
            f"* Cost per run ${u['mean_cost_usd']:.2f} (baseline ${u['baseline_mean_cost_usd']:.2f}); "
            f"tool calls per question {u['mean_tool_calls']:.1f} (baseline {u['baseline_mean_tool_calls']:.1f}); "
            f"turns per question {u['mean_turns']:.1f} (baseline {u['baseline_mean_turns']:.1f})."
        ),
        f"* Leak-scan hits: {report['leak_hits']}.",
        "",
    ]
    return "\n".join(lines)


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    fr = sub.add_parser(
        "freeze", help="write baseline_freeze.json from the baseline runs"
    )
    fr.add_argument("--runs", nargs="+", default=list(BASELINE_RUNS))
    ck = sub.add_parser(
        "check", help="check candidate runs against the frozen baseline"
    )
    ck.add_argument("run_dirs", nargs="+", type=Path)
    ck.add_argument(
        "--out", type=Path, help="report folder (default: the only candidate run)"
    )
    args = ap.parse_args()

    if args.cmd == "freeze":
        freeze = build_freeze([load_run(RUNS / name) for name in args.runs])
        write_json(FREEZE_PATH, freeze)
        s = freeze["summary"]
        print(
            f"froze {len(freeze['question_ids'])} questions from {', '.join(freeze['runs'])}: "
            f"mean {100 * s['mean_accuracy']:.1f}%, sd {100 * s['sd_accuracy']:.1f} pts"
        )
        return

    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    out = args.out or (args.run_dirs[0] if len(args.run_dirs) == 1 else None)
    if out is None:
        sys.exit("pass --out when checking more than one run")
    report = check(args.run_dirs, freeze)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "gate_report.json", report)
    (out / "gate_report.md").write_text(render(report), encoding="utf-8")
    print(
        f"gate {'PASS' if report['passed'] else 'FAIL'}; report in {out / 'gate_report.md'}"
    )
    for line in report["failures"] + report["warnings"]:
        print(f"  {line}")
    sys.exit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
