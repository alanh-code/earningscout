#!/usr/bin/env python3
"""Judge runner: three independent grades of closed-book answers.

The judge sees the question, official answer, rubric, model answer, and the
grading guide. It never sees the human grades. The default model is the
judge model in agent/llm.py (DeepSeek V4 Pro), with thinking on. By default it grades the frozen human-graded 15 and writes
agreement.md. Pass --answers-dir to grade another answer folder and skip
the human comparison.

Usage:
  .venv/bin/python evals/contamination/closed_book/judge/run_judge.py --dry-run
  .venv/bin/python evals/contamination/closed_book/judge/run_judge.py --name my-run
  .venv/bin/python evals/contamination/closed_book/judge/run_judge.py --name noleak-calibration --prompt evals/contamination/closed_book/judge/judge_prompt_noleak.md
  .venv/bin/python evals/contamination/closed_book/judge/run_judge.py --compare-only --run-dir evals/contamination/closed_book/judge/runs/noleak-calibration
  .venv/bin/python evals/contamination/closed_book/judge/run_judge.py --name selected --answers-dir evals/contamination/closed_book/runs/selected --prompt evals/contamination/closed_book/judge/judge_prompt_strict.md --guide evals/contamination/closed_book/grading_guide_strict.md
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import llm  # noqa: E402
from agent.protocol import SEED  # noqa: E402

VALS = ROOT / "data" / "vals" / "public.csv"
CLOSED = ROOT / "evals" / "contamination" / "closed_book"
JUDGE = Path(__file__).resolve().parent
GUIDE = CLOSED / "grading_guide.md"
PROMPT = JUDGE / "judge_prompt.md"
RUNS = JUDGE / "runs"
HUMAN_GRADES = CLOSED / "runs" / "batch-1" / "grades_human.csv"
ANSWER_RUNS = [
    CLOSED / "runs" / "batch-1",
    CLOSED / "runs" / "batch-2",
]

PASSES = 3
# Thinking tokens count toward the limit, so it is higher than the visible JSON needs.
MAX_TOKENS = 32768
COST_CAP_USD = 10.0
CSV_FIELDS = [
    "question_id",
    "check_id",
    "operator",
    "criteria",
    "result",
    "overall",
    "reason",
]

RESULT_CANON = {
    "met": "met",
    "not_met": "not met",
    "not met": "not met",
    "triggered": "triggered",
    "not_triggered": "not triggered",
    "not triggered": "not triggered",
}
POSITIVE = {"met", "triggered"}
OVERALL_LABELS = ("right", "wrong", "abstain")


def cost_usd(
    tokens_in: int,
    tokens_out: int,
    model: str | None = None,
    cached_in: int = 0,
    cache_write: int = 0,
) -> float:
    """Off-peak list cost from token totals (runs refuse to start in peak hours)."""
    cached_in = min(max(cached_in, 0), tokens_in)
    usage = {
        "cache_hit_tokens": cached_in,
        "cache_miss_tokens": max(tokens_in - cached_in, 0),
        "output_tokens": tokens_out,
    }
    return llm.cost_usd(model or llm.JUDGE_MODEL, usage)


def price_caption(model: str | None) -> str:
    return llm.price_caption(model or llm.JUDGE_MODEL)


def norm_ws(text: str) -> str:
    return " ".join((text or "").split())


def answer_text(response: dict) -> str:
    return llm.response_text(response)


def load_official() -> list[dict]:
    with VALS.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_model_answers() -> dict[str, dict]:
    found = {}
    for run_dir in ANSWER_RUNS:
        for path in sorted(run_dir.glob("vals-*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            qid = payload["question_id"]
            if qid in found:
                sys.exit(f"{qid} appears in more than one answer run")
            found[qid] = {
                "id": qid,
                "type": payload.get("question_type", ""),
                "question": payload["question"],
                "model_answer": answer_text(payload["response"]),
                "source_run": run_dir.name,
            }
    return found


def load_items_from_answer_dir(run_dir: Path) -> list[dict]:
    """Grade a single closed-book run with no human reference."""
    run_dir = run_dir.resolve()
    if not run_dir.is_dir():
        sys.exit(f"answers dir not found: {run_dir}")
    official_rows = load_official()
    items = []
    for path in sorted(run_dir.glob("vals-*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        qid = payload["question_id"]
        index = int(qid.split("-")[1])
        official = official_rows[index - 1]
        if official["Question"] != payload["question"]:
            sys.exit(f"{qid}: run JSON does not match data/vals/public.csv")
        rubric = json.loads(official["Rubric"])
        if not isinstance(rubric, list):
            sys.exit(f"{qid}: rubric is not a JSON list")
        items.append(
            {
                "id": qid,
                "type": official["Question Type"],
                "question": official["Question"],
                "answer": official["Answer"],
                "rubric": rubric,
                "model_answer": answer_text(payload["response"]),
                "source_run": run_dir.name,
            }
        )
    if not items:
        sys.exit(f"no vals-*.json answers in {run_dir}")
    return items


def load_items() -> list[dict]:
    official_rows = load_official()
    answers = load_model_answers()
    order = list(dict.fromkeys(row["question_id"] for row in load_human_rows()))
    items = []
    for qid in order:
        if qid not in answers:
            sys.exit(f"{qid} is in the human grades but has no model-answer JSON")
        index = int(qid.split("-")[1])
        official = official_rows[index - 1]
        rec = answers[qid]
        if official["Question"] != rec["question"]:
            sys.exit(f"{qid}: run JSON does not match data/vals/public.csv")
        rubric = json.loads(official["Rubric"])
        if not isinstance(rubric, list):
            sys.exit(f"{qid}: rubric is not a JSON list")
        items.append(
            {
                "id": qid,
                "type": official["Question Type"],
                "question": official["Question"],
                "answer": official["Answer"],
                "rubric": rubric,
                "model_answer": rec["model_answer"],
                "source_run": rec["source_run"],
            }
        )
    return items


def load_human_rows() -> list[dict]:
    with HUMAN_GRADES.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_human() -> dict[str, dict]:
    questions: dict[str, dict] = {}
    for row in load_human_rows():
        qid = row["question_id"]
        rec = questions.setdefault(
            qid, {"overall": row["overall"], "reason": row["reason"], "checks": {}}
        )
        rec["checks"][int(row["check_id"])] = {
            "operator": row["operator"],
            "criteria": row["criteria"],
            "result": RESULT_CANON[row["result"]],
        }
        if row["overall"] and rec["overall"] != row["overall"]:
            sys.exit(f"{qid}: the human overall label is not consistent across checks")
    return questions


def build_prompt(item: dict, template: str, guide: str) -> str:
    rubric_json = json.dumps(item["rubric"], ensure_ascii=False, indent=2)
    return (
        template.replace("{{grading_guide}}", guide)
        .replace("{{question}}", item["question"])
        .replace("{{official_answer}}", item["answer"])
        .replace("{{rubric}}", rubric_json)
        .replace("{{model_answer}}", item["model_answer"])
    )


def build_request(model: str, prompt: str, seed: int | None = SEED) -> dict:
    # Thinking on, so temperature does not apply. The judge never receives the
    # human grades; the prompt has only the guide and the item.
    return llm.build_request(
        model,
        [{"role": "user", "content": prompt}],
        max_tokens=MAX_TOKENS,
        thinking=True,
        seed=seed,
    )


def extract_json(text: str) -> dict:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("empty text")
    candidates = [raw]
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fenced:
        candidates.append(fenced.group(1).strip())
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        candidates.append(raw[start : end + 1])
    seen = set()
    errors = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as exc:
            errors.append(str(exc))
            continue
        if isinstance(data, dict):
            return data
        errors.append("JSON root is not an object")
    raise ValueError("; ".join(errors) or "no JSON object found")


def validate_grade(item: dict, data: dict) -> list[str]:
    warnings = []
    required = {
        "checks",
        "correctness_met",
        "correctness_total",
        "rubric_fraction",
        "contradiction_triggered",
        "overall",
        "reason",
    }
    missing = required - set(data)
    if missing:
        raise ValueError(f"missing fields {sorted(missing)}")
    if data["overall"] not in OVERALL_LABELS:
        raise ValueError(f"invalid overall {data['overall']!r}")
    checks = data["checks"]
    if not isinstance(checks, list):
        raise TypeError(f"expected checks to be a list, got {type(checks)}")
    if len(checks) != len(item["rubric"]):
        raise ValueError(f"expected {len(item['rubric'])} checks, got {len(checks)}")
    for i, (got, expected) in enumerate(
        zip(checks, item["rubric"], strict=True), start=1
    ):
        if not isinstance(got, dict):
            raise TypeError(f"check {i} is not an object")
        if got.get("operator") != expected["operator"]:
            raise ValueError(
                f"check {i}: operator {got.get('operator')!r} != {expected['operator']!r}"
            )
        result = got.get("result")
        if expected["operator"] == "correctness":
            allowed = {"met", "not_met", "not met"}
        else:
            allowed = {"triggered", "not_triggered", "not triggered"}
        if result not in allowed:
            raise ValueError(
                f"check {i}: invalid {expected['operator']} result {result!r}"
            )
        if "result" in got:
            got["result"] = RESULT_CANON[result]
        if norm_ws(str(got.get("criteria", ""))) != norm_ws(expected["criteria"]):
            warnings.append(f"check {i}: criteria text drifted; aligned by index")
            got["criteria"] = expected["criteria"]
        else:
            got["criteria"] = expected["criteria"]
        got["id"] = i
        got["operator"] = expected["operator"]
    return warnings


def consistency_flags(item: dict, data: dict) -> list[str]:
    flags = []
    checks = data["checks"]
    correctness = [c for c in checks if c["operator"] == "correctness"]
    contradiction = next(c for c in checks if c["operator"] == "contradiction")
    met = sum(c["result"] == "met" for c in correctness)
    total = len(correctness)
    triggered = contradiction["result"] == "triggered"
    if int(data.get("correctness_met", -1)) != met:
        flags.append(
            f"correctness_met stated {data.get('correctness_met')} vs {met} from checks"
        )
    if int(data.get("correctness_total", -1)) != total:
        flags.append(
            f"correctness_total stated {data.get('correctness_total')} vs {total} from checks"
        )
    stated_frac = data.get("rubric_fraction")
    expected_frac = (met / total) if total else 0.0
    try:
        # Judges often round the stated fraction (0.2727 for 3/11), so allow rounding.
        if abs(float(stated_frac) - expected_frac) > 5e-4:
            flags.append(
                f"rubric_fraction stated {stated_frac} vs {expected_frac:.4f} from checks"
            )
    except (TypeError, ValueError):
        flags.append(f"rubric_fraction is not a number: {stated_frac!r}")
    if bool(data.get("contradiction_triggered")) != triggered:
        flags.append(
            f"contradiction_triggered stated {data.get('contradiction_triggered')} vs {triggered} from checks"
        )
    overall = data["overall"]
    if overall == "right" and (met != total or triggered):
        flags.append(
            "overall is right but some correctness checks failed or contradiction triggered"
        )
    if overall == "abstain" and (met or triggered):
        flags.append(
            "overall is abstain but a correctness check was met or contradiction triggered"
        )
    if triggered and overall != "wrong":
        flags.append(f"contradiction triggered but overall is {overall}")
    return flags


def csv_rows(item: dict, data: dict) -> list[dict]:
    reason = str(data.get("reason") or "").strip()
    overall = data["overall"]
    rows = []
    for check in data["checks"]:
        rows.append(
            {
                "question_id": item["id"],
                "check_id": check["id"],
                "operator": check["operator"],
                "criteria": check["criteria"],
                "result": check["result"],
                "overall": overall,
                "reason": reason,
            }
        )
    return rows


def write_grades(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def load_grade_csv(path: Path) -> dict[str, dict]:
    questions: dict[str, dict] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            qid = row["question_id"]
            rec = questions.setdefault(
                qid, {"overall": row["overall"], "reason": row["reason"], "checks": {}}
            )
            rec["checks"][int(row["check_id"])] = {
                "operator": row["operator"],
                "criteria": row["criteria"],
                "result": RESULT_CANON[row["result"]],
                "note": "",
            }
    return questions


def attach_notes(grades: dict[str, dict], raw_dir: Path) -> None:
    for path in raw_dir.glob("vals-*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        qid = payload["question_id"]
        if qid not in grades or not payload.get("ok"):
            continue
        parsed = payload.get("parsed") or {}
        for check in parsed.get("checks", []):
            cid = int(check["id"])
            if cid in grades[qid]["checks"]:
                grades[qid]["checks"][cid]["note"] = str(
                    check.get("note") or ""
                ).strip()


def _int_usage(*values) -> int:
    for value in values:
        if value is not None and value != "":
            return int(value)
    return 0


def usage_of(response: dict) -> tuple[int, int, int, int]:
    usage = response.get("usage") or {}
    tokens_in = _int_usage(usage.get("input_tokens"), usage.get("prompt_tokens"))
    tokens_out = _int_usage(usage.get("output_tokens"), usage.get("completion_tokens"))
    details = (
        usage.get("input_tokens_details") or usage.get("prompt_tokens_details") or {}
    )
    cached_in = _int_usage(
        details.get("cached_tokens"),
        details.get("cache_read_tokens"),
        usage.get("cache_read_input_tokens"),
    )
    cache_write = _int_usage(
        details.get("cache_write_tokens"),
        details.get("cache_creation_tokens"),
        usage.get("cache_creation_input_tokens"),
    )
    return tokens_in, tokens_out, cached_in, cache_write


def is_truncated(response: dict) -> bool:
    if "choices" in response:
        return llm.finish_reason(response) == "length"
    return response.get("stop_reason") == "max_tokens"


def call(client, request: dict) -> dict:
    """One judge call. `client` is unused and kept for the legacy call signature."""
    return llm.send(request)["response"]


def grade_one(client, request: dict, item: dict) -> tuple[dict, dict, list[str], bool]:
    """Parse and validate. Retry once on a parse or validation failure."""
    last_error: Exception | None = None
    response: dict = {}
    for attempt in (1, 2):
        response = call(client, request)
        try:
            if is_truncated(response):
                raise ValueError("response was truncated at the token limit")
            parsed = extract_json(answer_text(response))
            warnings = validate_grade(item, parsed)
            return response, parsed, warnings, attempt == 2
        except (ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt == 2:
                raise
    raise last_error or RuntimeError("grade_one exited without a result")


def cohen_kappa(left: list[str], right: list[str], labels: list[str]) -> float | None:
    n = len(left)
    if n == 0 or n != len(right):
        return None
    po = sum(a == b for a, b in zip(left, right, strict=True)) / n
    pe = 0.0
    for label in labels:
        pe += (sum(x == label for x in left) / n) * (sum(x == label for x in right) / n)
    if pe == 1:
        return 1.0 if po == 1 else 0.0
    return (po - pe) / (1 - pe)


def fmt_pct(num: int, den: int) -> str:
    if den == 0:
        return "n/a"
    return f"{100 * num / den:.1f}% ({num}/{den})"


def fmt_kappa(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}"


def majority_label(values: list[str]) -> tuple[str, bool]:
    counts = Counter(values)
    top = counts.most_common()
    if len(top) == 1 or top[0][1] > top[1][1]:
        return top[0][0], False
    # 1-1-1 (or other tie): use the first pass, and flag it.
    return values[0], True


def binary(result: str) -> str:
    return "positive" if result in POSITIVE else "negative"


def looks_numeric(text: str) -> bool:
    return bool(re.search(r"\d", text or ""))


def rule_note(
    operator: str,
    criteria: str,
    human_result: str,
    judge_results: list[str],
    human_overall: str,
    judge_overalls: list[str],
) -> str:
    if operator == "overall":
        if "abstain" in {human_overall, *judge_overalls}:
            return "Abstain rule: refusal vs a committed answer."
        if human_overall == "right" or "right" in judge_overalls:
            return "Overall right requires every correctness check met and no contradiction."
        return "Overall label."
    if operator == "contradiction":
        return "Contradiction triggers only on a conflicting claim, not on omission."
    if looks_numeric(criteria):
        return "Loose match for numbers, units, or dates, including the nearby-value guard."
    if re.search(
        r"\b(flat|declin|increas|substantial|retained|churn)\b", criteria, re.IGNORECASE
    ):
        return "Names and qualitative claims: meaning must be preserved."
    return "Correctness: stated fact must match the official meaning."


def iter_checks(items: list[dict]):
    for item in items:
        for i, check in enumerate(item["rubric"], start=1):
            yield item["id"], i, check


def compare_metrics(human: dict, judge: dict, items: list[dict]) -> dict:
    overall_a, overall_j = [], []
    check_a, check_j = [], []
    for item in items:
        qid = item["id"]
        overall_a.append(human[qid]["overall"])
        overall_j.append(judge[qid]["overall"])
        for cid, _ in enumerate(item["rubric"], start=1):
            check_a.append(binary(human[qid]["checks"][cid]["result"]))
            check_j.append(binary(judge[qid]["checks"][cid]["result"]))
    overall_agree = sum(a == b for a, b in zip(overall_a, overall_j, strict=True))
    check_agree = sum(a == b for a, b in zip(check_a, check_j, strict=True))
    return {
        "overall_agree": overall_agree,
        "overall_n": len(overall_a),
        "overall_kappa": cohen_kappa(overall_a, overall_j, list(OVERALL_LABELS)),
        "check_agree": check_agree,
        "check_n": len(check_a),
        "check_kappa": cohen_kappa(check_a, check_j, ["positive", "negative"]),
    }


def self_consistency(passes: list[dict[str, dict]], items: list[dict]) -> dict:
    overall_same = 0
    check_same = 0
    check_n = 0
    for item in items:
        qid = item["id"]
        labels = [p[qid]["overall"] for p in passes]
        overall_same += int(len(set(labels)) == 1)
        for cid, _ in enumerate(item["rubric"], start=1):
            results = [p[qid]["checks"][cid]["result"] for p in passes]
            check_same += int(len(set(results)) == 1)
            check_n += 1
    return {
        "overall_same": overall_same,
        "overall_n": len(items),
        "check_same": check_same,
        "check_n": check_n,
    }


def build_majority(
    passes: list[dict[str, dict]], items: list[dict]
) -> tuple[dict[str, dict], list[str]]:
    majority: dict[str, dict] = {}
    ties = []
    for item in items:
        qid = item["id"]
        labels = [p[qid]["overall"] for p in passes]
        overall, tied = majority_label(labels)
        if tied:
            ties.append(qid)
        reason = next(p[qid]["reason"] for p in passes if p[qid]["overall"] == overall)
        checks = {}
        for cid, check in enumerate(item["rubric"], start=1):
            results = [p[qid]["checks"][cid]["result"] for p in passes]
            result, check_tied = majority_label(results)
            if check_tied:
                ties.append(f"{qid} check {cid}")
            checks[cid] = {
                "operator": check["operator"],
                "criteria": check["criteria"],
                "result": result,
                "note": next(
                    (p[qid]["checks"][cid].get("note") or "")
                    for p in passes
                    if p[qid]["checks"][cid]["result"] == result
                ),
            }
        majority[qid] = {"overall": overall, "reason": reason, "checks": checks}
    return majority, ties


def write_agreement(
    path: Path,
    name: str,
    model: str,
    items: list[dict],
    human: dict,
    passes: list[dict[str, dict]],
    majority: dict[str, dict],
    ties: list[str],
    tokens_in: int,
    tokens_out: int,
    retries: int,
    failures: list[str],
    flags: list[str],
    prompt_label: str = "",
    guide_label: str = "",
    cached_in: int = 0,
    cache_write: int = 0,
) -> None:
    per_run = [compare_metrics(human, p, items) for p in passes]
    majority_metrics = compare_metrics(human, majority, items)
    consistency = self_consistency(passes, items)
    cost = cost_usd(tokens_in, tokens_out, model, cached_in, cache_write)
    lines = [
        f"# Judge agreement — {name}",
        "",
        f"Model `{model}`, 3 independent passes over {len(items)} closed-book answers, thinking on (temperature does not apply), seed {SEED} plus the pass number.",
        f"Prompt template: `{prompt_label or 'evals/contamination/closed_book/judge/judge_prompt.md'}`. Grading guide: `{guide_label or 'evals/contamination/closed_book/grading_guide.md'}`. The judge saw the grading guide, question, official answer, rubric, model answer, and any worked examples in the prompt. It did not see the human reference grades. Those grades were not changed.",
        f"Tokens: {tokens_in} in, {tokens_out} out. Cost about ${cost:.4f} at {price_caption(model)}. Parse retries: {retries}. Failures: {len(failures)}.",
        "",
        f"n={len(items)} makes kappa noisy; treat the percentages as the main figures.",
        "",
        "## Agreement with the human grader",
        "",
        "| Compare | Overall agreement | Overall kappa (3-class) | Check agreement | Check kappa (binary) |",
        "|---|---:|---:|---:|---:|",
    ]
    for i, m in enumerate(per_run, start=1):
        lines.append(
            f"| Run {i} vs human | {fmt_pct(m['overall_agree'], m['overall_n'])} | {fmt_kappa(m['overall_kappa'])} | "
            f"{fmt_pct(m['check_agree'], m['check_n'])} | {fmt_kappa(m['check_kappa'])} |"
        )
    lines.append(
        f"| Majority vote vs human | {fmt_pct(majority_metrics['overall_agree'], majority_metrics['overall_n'])} | "
        f"{fmt_kappa(majority_metrics['overall_kappa'])} | {fmt_pct(majority_metrics['check_agree'], majority_metrics['check_n'])} | "
        f"{fmt_kappa(majority_metrics['check_kappa'])} |"
    )
    lines += [
        "",
        "Check-level kappa treats `met`/`triggered` as positive and `not met`/`not triggered` as negative.",
        "",
        "## Self-consistency across 3 runs",
        "",
        f"- Overall labels identical in all 3 runs: {fmt_pct(consistency['overall_same'], consistency['overall_n'])}",
        f"- Checks identical in all 3 runs: {fmt_pct(consistency['check_same'], consistency['check_n'])}",
    ]
    if ties:
        lines.append(f"- Majority ties (fell back to run 1): {', '.join(ties)}")
    else:
        lines.append("- Majority ties: none.")
    lines += [
        "",
        "## Overall labels",
        "",
        "| Question | human | Run 1 | Run 2 | Run 3 | Majority |",
        "|---|---|---|---|---|---|",
    ]
    for item in items:
        qid = item["id"]
        rows = [passes[i][qid]["overall"] for i in range(3)]
        lines.append(
            f"| {qid} | {human[qid]['overall']} | {rows[0]} | {rows[1]} | {rows[2]} | {majority[qid]['overall']} |"
        )

    disagreements = []
    for item in items:
        qid = item["id"]
        judge_overalls = [p[qid]["overall"] for p in passes]
        if human[qid]["overall"] != majority[qid]["overall"] or any(
            o != human[qid]["overall"] for o in judge_overalls
        ):
            disagreements.append(
                {
                    "question": qid,
                    "check": "overall",
                    "human": human[qid]["overall"],
                    "judge": ", ".join(
                        f"r{i}={lab}" for i, lab in enumerate(judge_overalls, start=1)
                    )
                    + f"; maj={majority[qid]['overall']}",
                    "reason": " | ".join(
                        dict.fromkeys(
                            p[qid]["reason"]
                            for p in passes
                            if p[qid]["overall"] != human[qid]["overall"]
                        )
                    )
                    or majority[qid]["reason"],
                    "note": rule_note(
                        "overall",
                        "",
                        human[qid]["overall"],
                        [],
                        human[qid]["overall"],
                        judge_overalls,
                    ),
                }
            )
        for cid, check in enumerate(item["rubric"], start=1):
            human_result = human[qid]["checks"][cid]["result"]
            judge_results = [p[qid]["checks"][cid]["result"] for p in passes]
            if human_result == majority[qid]["checks"][cid]["result"] and all(
                r == human_result for r in judge_results
            ):
                continue
            reasons = []
            for i, p in enumerate(passes, start=1):
                if p[qid]["checks"][cid]["result"] != human_result:
                    note = p[qid]["checks"][cid].get("note") or p[qid]["reason"]
                    if note:
                        reasons.append(f"r{i}: {note}")
            disagreements.append(
                {
                    "question": qid,
                    "check": f"{cid} ({check['operator']})",
                    "human": human_result,
                    "judge": ", ".join(
                        f"r{i}={res}" for i, res in enumerate(judge_results, start=1)
                    )
                    + f"; maj={majority[qid]['checks'][cid]['result']}",
                    "reason": " | ".join(reasons) or majority[qid]["reason"],
                    "note": rule_note(
                        check["operator"],
                        check["criteria"],
                        human_result,
                        judge_results,
                        human[qid]["overall"],
                        judge_overalls,
                    ),
                }
            )

    lines += [
        "",
        "## Disagreements with the human grader",
        "",
        "A row appears when any of the three runs, or the majority vote, differs from the human grader. Check-level reasons are the judge's per-check note when present, otherwise the one-line overall reason.",
        "",
        "| Question | Check | human | Judge grade(s) | Judge reason | Rule |",
        "|---|---|---|---|---|---|",
    ]
    if disagreements:
        for row in disagreements:
            lines.append(
                "| "
                + " | ".join(
                    _cell(row[k])
                    for k in ("question", "check", "human", "judge", "reason", "note")
                )
                + " |"
            )
    else:
        lines.append("| — | — | — | none | — | — |")

    if flags:
        lines += ["", "## Judge internal consistency", ""]
        lines.extend(f"- {flag}" for flag in flags)
    if failures:
        lines += ["", "## Failures", ""]
        lines.extend(f"- {fail}" for fail in failures)

    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def write_summary(
    path: Path,
    name: str,
    model: str,
    items: list[dict],
    tokens_in: int,
    tokens_out: int,
    retries: int,
    failures: list[str],
    prompt_label: str = "",
    guide_label: str = "",
    cached_in: int = 0,
    cache_write: int = 0,
) -> None:
    cost = cost_usd(tokens_in, tokens_out, model, cached_in, cache_write)
    lines = [
        f"# Judge run {name}",
        "",
        f"Model `{model}`, {len(items)} answers, {PASSES} independent passes, thinking on (temperature does not apply), seed {SEED} plus the pass number.",
        f"Prompt template: `{prompt_label or 'evals/contamination/closed_book/judge/judge_prompt.md'}`. Grading guide: `{guide_label or 'evals/contamination/closed_book/grading_guide.md'}`. Judge inputs: grading guide, question, official answer, rubric, model answer, and any worked examples in the prompt. Human reference grades were not sent.",
        f"Tokens: {tokens_in} in, {tokens_out} out. Cost about ${cost:.4f} at {price_caption(model)}.",
        f"Parse retries: {retries}. Failures: {len(failures)}.",
        "",
    ]
    if failures:
        lines += ["Failures:", ""] + [f"- {f}" for f in failures] + [""]
    path.write_text("\n".join(lines), encoding="utf-8")


def load_pass(run_dir: Path, items: list[dict], pass_i: int) -> dict[str, dict]:
    path = run_dir / f"judge_grades_run{pass_i}.csv"
    if not path.exists():
        sys.exit(f"missing {path}")
    grades = load_grade_csv(path)
    attach_notes(grades, run_dir / "raw" / f"run{pass_i}")
    missing = [item["id"] for item in items if item["id"] not in grades]
    if missing:
        sys.exit(f"run {pass_i} is missing grades for {missing}")
    return grades


def resolve_run_dir(raw: Path) -> Path:
    if raw.is_absolute():
        path = raw
    else:
        for candidate in ((Path.cwd() / raw).resolve(), (ROOT / raw).resolve()):
            if candidate.exists():
                return candidate
        path = (ROOT / raw).resolve()
    if not path.exists():
        sys.exit(f"run dir not found: {raw}")
    return path


def resolve_prompt_path(raw: Path | None) -> Path:
    if raw is None:
        return PROMPT
    if raw.is_absolute():
        return raw
    for candidate in (
        (Path.cwd() / raw).resolve(),
        (ROOT / raw).resolve(),
        (JUDGE / raw).resolve(),
    ):
        if candidate.exists():
            return candidate
    return (ROOT / raw).resolve()


def resolve_guide_path(raw: Path | None) -> Path:
    if raw is None:
        return GUIDE
    if raw.is_absolute():
        return raw
    for candidate in (
        (Path.cwd() / raw).resolve(),
        (ROOT / raw).resolve(),
        (CLOSED / raw).resolve(),
        (JUDGE / raw).resolve(),
    ):
        if candidate.exists():
            return candidate
    return (ROOT / raw).resolve()


def relative_label(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


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


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="load inputs and print prompt sizes, call nothing",
    )
    ap.add_argument(
        "--model",
        help="model id (default: the judge model in agent/llm.py, checked against the provider model list)",
    )
    ap.add_argument(
        "--run-dir",
        type=Path,
        help="existing judge run directory (for resume or --compare-only)",
    )
    ap.add_argument(
        "--compare-only",
        action="store_true",
        help="recompute agreement.md from a finished run",
    )
    ap.add_argument(
        "--prompt",
        type=Path,
        help="judge prompt template (default: judge/judge_prompt.md)",
    )
    ap.add_argument(
        "--guide",
        type=Path,
        help="grading guide (default: closed_book/grading_guide.md)",
    )
    ap.add_argument(
        "--cost-cap",
        type=float,
        default=COST_CAP_USD,
        help="stop if projected cost would exceed this USD amount (default: 10)",
    )
    ap.add_argument("--name", help="folder name under runs/ for a new judge run")
    ap.add_argument(
        "--allow-peak", action="store_true", help="run even in provider peak hours"
    )
    ap.add_argument(
        "--answers-dir",
        type=Path,
        help="closed-book answer folder to grade (skips human comparison)",
    )
    args = ap.parse_args()

    prompt_path = resolve_prompt_path(args.prompt)
    guide_path = resolve_guide_path(args.guide)
    compare_human = args.answers_dir is None
    if not guide_path.exists() or not prompt_path.exists():
        sys.exit("missing grading guide or judge prompt")
    if compare_human and not HUMAN_GRADES.exists():
        sys.exit("missing human grades")
    guide = guide_path.read_text(encoding="utf-8")
    template = prompt_path.read_text(encoding="utf-8")
    prompt_label = relative_label(prompt_path)
    guide_label = relative_label(guide_path)
    if args.answers_dir:
        items = load_items_from_answer_dir(args.answers_dir)
        human = {}
    else:
        items = load_items()
        human = load_human()
    if args.dry_run:
        print(f"{len(items)} answers, {PASSES} passes, guide {len(guide)} chars")
        for item in items:
            prompt = build_prompt(item, template, guide)
            print(
                f"{item['id']:>8}  {item['type']:<40}  "
                f"checks={len(item['rubric'])}  prompt_chars={len(prompt)}  "
                f"answer_chars={len(item['model_answer'])}  from {item['source_run']}"
            )
            if HUMAN_GRADES.name in prompt:
                sys.exit(
                    f"{item['id']}: prompt unexpectedly mentions the human grades file"
                )
        print(
            f"template {prompt_label}, guide {guide_label}, model to resolve at run time unless --model is set"
        )
        return

    client = None
    model = llm.resolve_model(args.model or llm.JUDGE_MODEL)
    if not args.compare_only:
        llm.require_off_peak([model], args.allow_peak)

    if args.compare_only:
        if not args.run_dir:
            sys.exit("--compare-only requires --run-dir")
        run_dir = resolve_run_dir(args.run_dir)
        meta_path = run_dir / "run_meta.json"
        tokens_in = tokens_out = cached_in = cache_write = retries = 0
        failures, flags = [], []
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            tokens_in = int(meta.get("tokens_in") or 0)
            tokens_out = int(meta.get("tokens_out") or 0)
            cached_in = int(meta.get("cached_input") or 0)
            cache_write = int(meta.get("cache_write") or 0)
            retries = int(meta.get("retries") or 0)
            failures = list(meta.get("failures") or [])
            flags = list(meta.get("flags") or [])
            model = meta.get("model") or model
            prompt_label = meta.get("prompt") or prompt_label
            guide_label = meta.get("guide") or guide_label
        passes = [load_pass(run_dir, items, i) for i in range(1, PASSES + 1)]
        majority, ties = build_majority(passes, items)
        write_grades(
            run_dir / "judge_grades_majority.csv",
            [
                row
                for item in items
                for row in csv_rows(
                    item,
                    {
                        "overall": majority[item["id"]]["overall"],
                        "reason": majority[item["id"]]["reason"],
                        "checks": [
                            {"id": cid, **majority[item["id"]]["checks"][cid]}
                            for cid, _ in enumerate(item["rubric"], start=1)
                        ],
                    },
                )
            ],
        )
        if compare_human:
            write_agreement(
                run_dir / "agreement.md",
                run_dir.name,
                model,
                items,
                human,
                passes,
                majority,
                ties,
                tokens_in,
                tokens_out,
                retries,
                failures,
                flags,
                prompt_label,
                guide_label=guide_label,
                cached_in=cached_in,
                cache_write=cache_write,
            )
            print(f"Wrote {(run_dir / 'agreement.md').relative_to(ROOT)}")
        return

    if args.run_dir:
        run_dir = resolve_run_dir(args.run_dir)
        name = run_dir.name
    else:
        if not args.name:
            sys.exit("a new run requires --name (a role name, not a timestamp)")
        name = run_folder_name(args.name)
        run_dir = RUNS / name
        if run_dir.exists() and any(run_dir.iterdir()):
            sys.exit(f"{run_dir} already exists; pass --run-dir to resume")
        run_dir.mkdir(parents=True)

    (run_dir / "prompt.md").write_text(template, encoding="utf-8")
    (run_dir / "grading_guide.md").write_text(guide, encoding="utf-8")

    tokens_in = tokens_out = cached_in = cache_write = retries = 0
    failures: list[str] = []
    flags: list[str] = []
    pass_rows: list[list[dict]] = [[] for _ in range(PASSES)]
    completed_calls = 0
    planned_calls = PASSES * len(items)
    stopped_for_cost = False

    for pass_i in range(1, PASSES + 1):
        raw_dir = run_dir / "raw" / f"run{pass_i}"
        raw_dir.mkdir(parents=True, exist_ok=True)
        for item in items:
            raw_path = raw_dir / f"{item['id']}.json"
            if raw_path.exists():
                saved = json.loads(raw_path.read_text(encoding="utf-8"))
                if saved.get("ok"):
                    saved_tokens = saved.get("tokens") or {}
                    tokens_in += int(saved_tokens.get("input") or 0)
                    tokens_out += int(saved_tokens.get("output") or 0)
                    cached_in += int(saved_tokens.get("cached_input") or 0)
                    cache_write += int(saved_tokens.get("cache_write") or 0)
                    retries += int(bool(saved.get("retried")))
                    flags.extend(
                        f"{item['id']} run {pass_i}: {flag}"
                        for flag in saved.get("flags") or []
                    )
                    pass_rows[pass_i - 1].extend(csv_rows(item, saved["parsed"]))
                    completed_calls += 1
                    print(
                        f"run{pass_i} {item['id']:>8} skipped (already ok)", flush=True
                    )
                    continue
            if stopped_for_cost:
                continue
            prompt = build_prompt(item, template, guide)
            if HUMAN_GRADES.name in prompt:
                sys.exit(
                    f"{item['id']}: prompt unexpectedly mentions the human grades file"
                )
            request = build_request(model, prompt, seed=SEED + pass_i - 1)
            try:
                response, parsed, warnings, retried = grade_one(client, request, item)
            except Exception as exc:  # noqa: BLE001 — record the failure and continue
                payload = {
                    "question_id": item["id"],
                    "pass": pass_i,
                    "model": model,
                    "ok": False,
                    "error": str(exc),
                    "request": request,
                }
                raw_path.write_text(
                    json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                failures.append(f"{item['id']} run {pass_i}: {exc}")
                print(f"run{pass_i} {item['id']:>8} FAILED  {exc}", flush=True)
                continue
            q_in, q_out, q_cached, q_write = usage_of(response)
            tokens_in += q_in
            tokens_out += q_out
            cached_in += q_cached
            cache_write += q_write
            retries += int(retried)
            completed_calls += 1
            item_flags = consistency_flags(item, parsed)
            flags.extend(f"{item['id']} run {pass_i}: {flag}" for flag in item_flags)
            item_cost = cost_usd(q_in, q_out, model, q_cached, q_write)
            running_cost = cost_usd(
                tokens_in, tokens_out, model, cached_in, cache_write
            )
            payload = {
                "question_id": item["id"],
                "pass": pass_i,
                "model": response.get("model") or model,
                "ok": True,
                "retried": retried,
                "warnings": warnings,
                "flags": item_flags,
                "tokens": {
                    "input": q_in,
                    "output": q_out,
                    "cached_input": q_cached,
                    "cache_write": q_write,
                },
                "cost_usd": item_cost,
                "parsed": parsed,
                "request": request,
                "response": response,
            }
            raw_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            pass_rows[pass_i - 1].extend(csv_rows(item, parsed))
            projected = running_cost / completed_calls * planned_calls
            print(
                f"run{pass_i} {item['id']:>8} done  in={q_in} out={q_out}  "
                f"cached={q_cached}  {parsed['overall']}{' retry' if retried else ''}  "
                f"${item_cost:.4f}  running ${running_cost:.4f}  projected ${projected:.4f}",
                flush=True,
            )
            if (
                args.cost_cap is not None
                and args.cost_cap > 0
                and projected > args.cost_cap
                and completed_calls >= 3
            ):
                stopped_for_cost = True
                failures.append(
                    f"stopped after {completed_calls}/{planned_calls} calls: "
                    f"projected ${projected:.4f} exceeds cost cap ${args.cost_cap:.2f} "
                    f"(running ${running_cost:.4f})"
                )
                print(failures[-1], flush=True)
        write_grades(run_dir / f"judge_grades_run{pass_i}.csv", pass_rows[pass_i - 1])

    if failures:
        write_summary(
            run_dir / "summary.md",
            name,
            model,
            items,
            tokens_in,
            tokens_out,
            retries,
            failures,
            prompt_label,
            guide_label=guide_label,
            cached_in=cached_in,
            cache_write=cache_write,
        )
        meta = {
            "model": model,
            "prompt": prompt_label,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cached_input": cached_in,
            "cache_write": cache_write,
            "retries": retries,
            "failures": failures,
            "flags": flags,
            "cost_usd": cost_usd(tokens_in, tokens_out, model, cached_in, cache_write),
        }
        (run_dir / "run_meta.json").write_text(
            json.dumps(meta, indent=2) + "\n", encoding="utf-8"
        )
        print(
            f"\n{len(failures)} failures; agreement.md not written. Saved to {run_dir.relative_to(ROOT)}"
        )
        sys.exit(1)

    passes = [load_pass(run_dir, items, i) for i in range(1, PASSES + 1)]
    majority, ties = build_majority(passes, items)
    write_grades(
        run_dir / "judge_grades_majority.csv",
        [
            row
            for item in items
            for row in csv_rows(
                item,
                {
                    "overall": majority[item["id"]]["overall"],
                    "reason": majority[item["id"]]["reason"],
                    "checks": [
                        {"id": cid, **majority[item["id"]]["checks"][cid]}
                        for cid, _ in enumerate(item["rubric"], start=1)
                    ],
                },
            )
        ],
    )
    if compare_human:
        write_agreement(
            run_dir / "agreement.md",
            name,
            model,
            items,
            human,
            passes,
            majority,
            ties,
            tokens_in,
            tokens_out,
            retries,
            failures,
            flags,
            prompt_label,
            guide_label=guide_label,
            cached_in=cached_in,
            cache_write=cache_write,
        )
    write_summary(
        run_dir / "summary.md",
        name,
        model,
        items,
        tokens_in,
        tokens_out,
        retries,
        failures,
        prompt_label,
        guide_label=guide_label,
        cached_in=cached_in,
        cache_write=cache_write,
    )
    meta = {
        "model": model,
        "prompt": prompt_label,
        "guide": guide_label,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cached_input": cached_in,
        "cache_write": cache_write,
        "retries": retries,
        "failures": failures,
        "flags": flags,
        "ties": ties,
        "cost_usd": cost_usd(tokens_in, tokens_out, model, cached_in, cache_write),
    }
    (run_dir / "run_meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"\nAll {PASSES} passes complete. Tokens: {tokens_in} in, {tokens_out} out. "
        f"Cost about ${cost_usd(tokens_in, tokens_out, model, cached_in, cache_write):.4f}.\n"
        f"Saved to {run_dir.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
