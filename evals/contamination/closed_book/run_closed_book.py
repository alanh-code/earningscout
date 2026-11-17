#!/usr/bin/env python3
"""Closed-book run: Claude Sonnet 5.5 answers the 10 frozen selected questions from memory.

Every call goes straight to the Anthropic Messages API, with no tools, no system
prompt and no files. The user message is only the question text. One fresh
request is used per question. Every response is checked, and the run stops on
the first closed-environment violation.

Usage:
  .venv/bin/python evals/contamination/closed_book/run_closed_book.py --dry-run
  .venv/bin/python evals/contamination/closed_book/run_closed_book.py --name batch-1
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VALS = ROOT / "data" / "vals" / "public.csv"
EVAL_DIR = ROOT / "evals" / "contamination"
SELECTED = EVAL_DIR / "questions.csv"
RUNS = EVAL_DIR / "closed_book" / "runs"

MODEL = "claude-sonnet-5-5"
API_URL = "https://api.anthropic.com"
MAX_TOKENS = 4096
PRICE_IN, PRICE_OUT = 2.00, 10.00  # USD per million tokens, same as the completion runs


class ClosedEnvironmentError(RuntimeError):
    pass


def api_key() -> str:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return value
    sys.exit("ANTHROPIC_API_KEY is not set in .env")


def resolve_questions_path(raw: Path) -> Path:
    if raw.is_absolute():
        path = raw
    else:
        for candidate in ((Path.cwd() / raw).resolve(), (ROOT / raw).resolve()):
            if candidate.exists():
                return candidate
        path = (Path.cwd() / raw).resolve()
    if not path.exists():
        sys.exit(f"questions file not found: {raw}")
    return path


def load_questions(selected_path: Path | None = None) -> list[dict]:
    selected_path = selected_path or SELECTED
    with VALS.open(newline="", encoding="utf-8") as f:
        public = list(csv.DictReader(f))
    with selected_path.open(newline="", encoding="utf-8") as f:
        selected = list(csv.DictReader(f))
    items = []
    for row in selected:
        index = int(row["id"].split("-")[1])
        official = public[index - 1]
        if official["Question"] != row["Question"]:
            sys.exit(f"{row['id']}: questions.csv does not match data/vals/public.csv")
        rubric = json.loads(official["Rubric"])
        if not isinstance(rubric, list):
            sys.exit(f"{row['id']}: rubric is not a JSON list")
        items.append(
            {
                "id": row["id"],
                "type": official["Question Type"],
                "question": official["Question"],
                "answer": official["Answer"],
                "rubric": rubric,
            }
        )
    return items


def build_request(question: str) -> dict:
    # No tools, no system prompt, no files. Thinking off, same as the completion runs.
    return {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "thinking": {"type": "between_tools"},
        "messages": [{"role": "user", "content": question}],
    }


def check_closed(request: dict, response: dict) -> None:
    problems = []
    extra = set(request) - {"model", "max_tokens", "thinking", "messages"}
    if extra:
        problems.append(f"unexpected request fields {sorted(extra)}")
    if "tools" in request or "system" in request:
        problems.append("request includes tools or a system prompt")
    if len(request.get("messages") or []) != 1:
        problems.append("request is not a single fresh message")
    message = (request.get("messages") or [{}])[0]
    if message.get("role") != "user" or not isinstance(message.get("content"), str):
        problems.append("user message is not plain question text")
    types = [b.get("type") for b in response.get("content", [])]
    if not types:
        problems.append("response has no content blocks")
    if any(t != "text" for t in types):
        problems.append(f"non text content blocks {types}")
    if "tool_use" in types or "server_tool_use" in types:
        problems.append(f"tool content blocks {types}")
    if response.get("stop_reason") == "tool_use":
        problems.append("stop_reason is tool_use")
    server_tools = (response.get("usage") or {}).get("server_tool_use") or {}
    if isinstance(server_tools, dict):
        used = {
            k: v for k, v in server_tools.items() if isinstance(v, (int, float)) and v
        }
        if used:
            problems.append(f"server tool use {used}")
    elif server_tools:
        problems.append(f"server tool use {server_tools}")
    if problems:
        raise ClosedEnvironmentError("; ".join(problems))


def cost_usd(tokens_in: int, tokens_out: int) -> float:
    return tokens_in / 1e6 * PRICE_IN + tokens_out / 1e6 * PRICE_OUT


def answer_text(response: dict) -> str:
    return "".join(
        block.get("text", "")
        for block in response.get("content", [])
        if block.get("type") == "text"
    )


def fence(text: str) -> str:
    ticks = "```"
    while ticks in text:
        ticks += "`"
    return f"{ticks}text\n{text}\n{ticks}"


def write_grading_sheet(run_dir: Path, records: list[dict]) -> None:
    lines = [
        "Grade using the rules in `evals/contamination/closed_book/grading_guide.md`.",
        "",
    ]
    csv_rows = []
    for rec in records:
        qid = rec["id"]
        lines += [
            f"## {qid} — {rec['type']}",
            "",
            "**Question**",
            "",
            fence(rec["question"]),
            "",
            "**Model answer**",
            "",
            fence(rec["model_answer"]),
            "",
            "**Official answer**",
            "",
            fence(rec["answer"]),
            "",
            "**Rubric checks**",
            "",
        ]
        for i, check in enumerate(rec["rubric"], start=1):
            operator = check["operator"]
            criteria = check["criteria"]
            lines.append(f"{i}. `{operator}`: {criteria}")
            if operator == "contradiction":
                lines.append("   - [ ] triggered")
                lines.append("   - [ ] not triggered")
            else:
                lines.append("   - [ ] met")
                lines.append("   - [ ] not met")
            lines.append("")
            csv_rows.append(
                {
                    "question_id": qid,
                    "check_id": i,
                    "operator": operator,
                    "criteria": criteria,
                    "result": "",
                    "overall": "",
                    "reason": "",
                }
            )
        lines += [
            "**Overall grade:** [ ] right  [ ] wrong  [ ] abstain",
            "",
            "**Reason:**",
            "",
            "________________________________",
            "",
        ]
    (run_dir / "grading_sheet.md").write_text("\n".join(lines), encoding="utf-8")
    with (run_dir / "grades_human.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
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
        writer.writeheader()
        writer.writerows(csv_rows)


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


def write_summary(
    run_dir: Path, name: str, records: list[dict], tokens_in: int, tokens_out: int
) -> None:
    total_cost = cost_usd(tokens_in, tokens_out)
    lines = [
        f"# Closed-book run {name}",
        "",
        f"Model `{MODEL}`, {len(records)} questions, one fresh request each.",
        "No tools, no system prompt, no files. User message was only the question text.",
        f"All {len(records)} responses passed the closed-environment checks.",
        f"Tokens: {tokens_in} in, {tokens_out} out. Cost about ${total_cost:.4f} at ${PRICE_IN:.2f}/${PRICE_OUT:.2f} per million input/output tokens.",
        "",
        "This file has no grades.",
        "",
        "| id | type | stop_reason | input tokens | output tokens | cost USD |",
        "|---|---|---|---|---|---|",
    ]
    for rec in records:
        lines.append(
            f"| {rec['id']} | {rec['type']} | {rec['stop_reason']} | "
            f"{rec['tokens_in']} | {rec['tokens_out']} | ${rec['cost']:.6f} |"
        )
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def call(client, request: dict) -> dict:
    return client.messages.create(**request).model_dump(mode="json")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="print questions, call nothing"
    )
    ap.add_argument(
        "--questions",
        type=Path,
        default=SELECTED,
        help="CSV of questions to run (default: evals/contamination/questions.csv)",
    )
    ap.add_argument("--name", help="folder name under runs/ for a new run")
    args = ap.parse_args()

    items = load_questions(resolve_questions_path(args.questions))
    if args.dry_run:
        for q in items:
            print(f"{q['id']}  {q['type']}\n  {q['question']}\n")
        print(f"{len(items)} questions, model {MODEL}, max_tokens {MAX_TOKENS}")
        return

    if not args.name:
        sys.exit("a new run requires --name (a role name, not a timestamp)")

    import anthropic

    client = anthropic.Anthropic(api_key=api_key(), base_url=API_URL)
    name = run_folder_name(args.name)
    run_dir = RUNS / name
    if run_dir.exists() and any(run_dir.iterdir()):
        sys.exit(f"{run_dir} already exists")
    run_dir.mkdir(parents=True)

    records = []
    tokens_in = tokens_out = 0
    for q in items:
        request = build_request(q["question"])
        response = call(client, request)
        check_closed(request, response)
        usage = response.get("usage") or {}
        q_in = int(usage.get("input_tokens") or 0)
        q_out = int(usage.get("output_tokens") or 0)
        tokens_in += q_in
        tokens_out += q_out
        rec = {
            "id": q["id"],
            "type": q["type"],
            "question": q["question"],
            "answer": q["answer"],
            "rubric": q["rubric"],
            "model_answer": answer_text(response),
            "stop_reason": response.get("stop_reason"),
            "tokens_in": q_in,
            "tokens_out": q_out,
            "cost": cost_usd(q_in, q_out),
        }
        payload = {
            "question_id": q["id"],
            "question_type": q["type"],
            "question": q["question"],
            "model": response.get("model") or MODEL,
            "tokens": {"input": q_in, "output": q_out},
            "cost_usd": rec["cost"],
            "request": request,
            "response": response,
        }
        (run_dir / f"{q['id']}.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        records.append(rec)
        print(f"{q['id']:>8} done  in={q_in} out={q_out}", flush=True)

    write_summary(run_dir, name, records, tokens_in, tokens_out)
    write_grading_sheet(run_dir, records)
    total_cost = cost_usd(tokens_in, tokens_out)
    print(
        f"\nAll {len(records)} passed the closed-environment checks. "
        f"Tokens: {tokens_in} in, {tokens_out} out. Cost about ${total_cost:.4f}.\n"
        f"Saved to {run_dir.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
