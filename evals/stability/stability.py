"""Run-to-run stability of the agent across repeated runs of the same configuration.

  .venv/bin/python evals/stability/stability.py RUN RUN RUN [--json OUT]

Per scored question: pass rate, whether the final outcome (right or wrong) is the same in every
run, and whether the final answer is the same. An answer is reduced to a key: the numbers (bold
ones when there are any) and verdict labels in its headline, the first paragraph that has any,
with units and scale words normalized, bare years dropped and numbers rounded to three
significant figures. Answers with no number or label
in them have no key and are left out of the answer-agreement count.

Summary: score mean and SD, questions with the same outcome in every run, questions that flip,
questions with the same answer key in every run, and flips where the answer key did not change
(grading noise rather than agent noise).
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "evals" / "baseline" / "agent_loop" / "runs"

SCALES = {
    "k": 1e3, "thousand": 1e3,
    "m": 1e6, "mm": 1e6, "mn": 1e6, "million": 1e6, "millions": 1e6,
    "b": 1e9, "bn": 1e9, "billion": 1e9, "billions": 1e9,
    "t": 1e12, "tn": 1e12, "trillion": 1e12,
}
UNITS = {"%": "%", "percent": "%", "bps": "bps", "bp": "bps", "basis points": "bps", "x": "x"}
LABELS = {
    "beat": "beat", "beats": "beat", "exceeded": "beat",
    "miss": "miss", "missed": "miss", "misses": "miss",
    "in line": "met", "inline": "met", "met": "met",
}
NUMBER = re.compile(
    r"(?<![\w.\-/])(?P<neg>(?:^|(?<=\s))[-−]|\()?\$?(?P<num>\d[\d,]*(?:\.\d+)?)(?![\w-]*\d)(?!-[a-z])\s*"
    r"(?P<unit>%|percent|basis points|bps?\b|x\b|(?:thousand|millions?|billions?|trillion|mm|mn|bn|tn|[kmbt])\b)?",
    re.IGNORECASE,
)
MONTH = re.compile(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s*$", re.IGNORECASE)
ANSWER_LINE = re.compile(r"^\W*(?:final )?answer\b", re.IGNORECASE)
BOLD = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
LABEL = re.compile(r"\b(" + "|".join(sorted(LABELS, key=len, reverse=True)) + r")\b", re.IGNORECASE)


def _load_common():
    spec = importlib.util.spec_from_file_location("baseline_common", ROOT / "evals" / "baseline" / "common.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sig3(x: float) -> float:
    return 0.0 if x == 0 else round(x, 2 - math.floor(math.log10(abs(x))))


def numbers(text: str) -> list[tuple[float, str]]:
    """Normalized (value, unit) pairs; bare years and numbers glued to letters (Q4, FY2024, 10-K) are skipped."""
    out = []
    for m in NUMBER.finditer(text):
        value = float(m["num"].replace(",", ""))
        unit = (m["unit"] or "").lower()
        if not unit and value.is_integer() and (1900 <= value <= 2100 or MONTH.search(text[: m.start()])):
            continue
        if unit in SCALES:
            value, unit = value * SCALES[unit], ""
        if m["neg"]:
            value = -value
        out.append((sig3(value), UNITS.get(unit, unit)))
    return out


def answer_key(text: str) -> tuple | None:
    """Numbers and labels of the headline: an 'Answer:' paragraph if there is one, else the first
    paragraph that has any. Bold spans, when they hold a number, stand for the whole paragraph.
    None if no paragraph has a number or label."""
    paras = re.split(r"\n\s*\n", text or "")
    for para in [p for p in paras if ANSWER_LINE.match(p)] + paras:
        bold = " ; ".join(BOLD.findall(para))
        plain = para.replace("**", "")
        nums = numbers(bold) or numbers(plain)
        labels = {LABELS[m.lower()] for m in LABEL.findall(plain)}
        if nums or labels:
            return tuple(sorted(set(nums))), tuple(sorted(labels))
    return None


def load_run(run_dir: Path, exclusions: dict) -> dict[str, dict]:
    with (run_dir / "results.csv").open(newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["id"] not in exclusions]
    out = {}
    for r in rows:
        path = run_dir / "answers" / f"{r['id']}.json"
        answer = json.loads(path.read_text(encoding="utf-8")).get("model_answer", "") if path.exists() else ""
        out[r["id"]] = {"right": r["overall"] == "right", "key": answer_key(answer)}
    return out


def stability(runs: list[dict[str, dict]]) -> dict:
    ids = sorted(set.intersection(*(set(r) for r in runs)))
    scores = [sum(r[q]["right"] for q in ids) for r in runs]
    per_q = {}
    for q in ids:
        rights = [r[q]["right"] for r in runs]
        keys = [r[q]["key"] for r in runs]
        comparable = all(k is not None for k in keys)
        per_q[q] = {
            "pass_rate": sum(rights) / len(runs),
            "same_outcome": len(set(rights)) == 1,
            "comparable": comparable,
            "same_answer": comparable and len(set(keys)) == 1,
        }
    flips = [q for q, s in per_q.items() if not s["same_outcome"]]
    return {
        "n_runs": len(runs),
        "n_questions": len(ids),
        "scores": scores,
        "mean": statistics.mean(scores),
        "sd": statistics.stdev(scores) if len(scores) > 1 else 0.0,
        "same_outcome": sum(s["same_outcome"] for s in per_q.values()),
        "always_right": sum(s["pass_rate"] == 1 for s in per_q.values()),
        "flips": flips,
        "comparable": sum(s["comparable"] for s in per_q.values()),
        "same_answer": sum(s["same_answer"] for s in per_q.values()),
        "grading_flips": [q for q in flips if per_q[q]["same_answer"]],
        "per_question": per_q,
    }


def render(names: list[str], s: dict) -> str:
    return "\n".join([
        f"runs: {', '.join(names)}",
        f"scores: {s['scores']}  mean {s['mean']:.2f}  SD {s['sd']:.2f}  (of {s['n_questions']})",
        f"same outcome in every run: {s['same_outcome']}/{s['n_questions']}  (always right {s['always_right']})",
        f"flipping questions: {len(s['flips'])}  {' '.join(s['flips'])}",
        f"same answer key in every run: {s['same_answer']}/{s['comparable']} comparable",
        f"flips with an unchanged answer key (grading noise): {len(s['grading_flips'])}  {' '.join(s['grading_flips'])}",
    ])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+", help="run folder names under runs/ or paths")
    ap.add_argument("--json", type=Path, help="write the full result here")
    args = ap.parse_args()
    exclusions = _load_common().load_exclusions()
    dirs = [Path(r) if Path(r).is_dir() else RUNS / r for r in args.runs]
    result = stability([load_run(d, exclusions) for d in dirs])
    print(render([d.name for d in dirs], result))
    if args.json:
        args.json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
