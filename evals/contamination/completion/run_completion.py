#!/usr/bin/env python3
"""Completion test: does the model reproduce the hidden end of a benchmark question?

Each question is cut at about 60% of its words. The model sees the first part
and is asked for the rest, two ways:

  guided   names the source (the Vals AI Finance Agent public set)
  general  asks only to complete the question

Every call runs in a closed environment: the Anthropic Messages API directly,
no tools, no system prompt, no files, one fresh request per prompt, thinking
off. Every response is checked, and the run stops on the first violation.

Usage:
  .venv/bin/python evals/contamination/completion/run_completion.py --dry-run
  .venv/bin/python evals/contamination/completion/run_completion.py --ids vals-07
  .venv/bin/python evals/contamination/completion/run_completion.py --vals-only
  .venv/bin/python evals/contamination/completion/run_completion.py --name official
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
CONTROL = EVAL_DIR / "controls.csv"
SELECTED = EVAL_DIR / "questions.csv"
RUNS = EVAL_DIR / "completion" / "runs"

MODEL = "claude-sonnet-5-5"
API_URL = "https://api.anthropic.com"
MAX_TOKENS = 1024
CUT = 0.6
PRICE_IN, PRICE_OUT = 2.00, 10.00  # USD per million tokens
EMBED_MODEL = "all-mpnet-base-v2"

PROMPTS = {
    "guided": (
        "This is the beginning of a question from the Vals AI Finance Agent "
        "benchmark public set. Write how you think that question continues, as "
        "close to its original wording as you can. A guess is fine: it will be "
        "compared with the real question to measure recall. Reply with only "
        "the rest of the question, starting right after the given text.\n\n"
        "Beginning: {prefix}"
    ),
    "general": (
        "Complete this question. A guess is fine. Reply with only the rest of "
        "the question, starting right after the given text.\n\n"
        "Beginning: {prefix}"
    ),
}


class ClosedEnvironmentError(RuntimeError):
    pass


# Inputs


def load_questions(include_control: bool) -> list[dict]:
    with VALS.open(newline="", encoding="utf-8") as f:
        items = [
            {
                "id": f"vals-{i:02d}",
                "group": "vals",
                "type": r["Question Type"],
                "question": r["Question"],
            }
            for i, r in enumerate(csv.DictReader(f), start=1)
        ]
    if include_control:
        with CONTROL.open(newline="", encoding="utf-8") as f:
            items += [
                {
                    "id": f"ctrl-{i:02d}",
                    "group": "control",
                    "type": r["Question Type"],
                    "question": r["Question"],
                }
                for i, r in enumerate(csv.DictReader(f), start=1)
            ]
    return items


def cut(question: str, share: float = CUT) -> tuple[str, str]:
    words = question.split()
    k = max(1, min(len(words) - 1, round(len(words) * share)))
    return " ".join(words[:k]), " ".join(words[k:])


def api_key() -> str:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return value
    sys.exit("ANTHROPIC_API_KEY is not set in .env")


# Closed environment


def build_request(prompt: str) -> dict:
    # No tools, no system prompt, no files. Thinking off, so the answer is recall only.
    return {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "thinking": {"type": "between_tools"},
        "messages": [{"role": "user", "content": prompt}],
    }


def check_closed(request: dict, response: dict) -> None:
    problems = []
    if set(request) - {"model", "max_tokens", "thinking", "messages"}:
        problems.append(f"unexpected request fields {sorted(set(request))}")
    if len(request["messages"]) != 1:
        problems.append("request is not a single fresh message")
    types = [b.get("type") for b in response.get("content", [])]
    if any(t != "text" for t in types):
        problems.append(f"non text content blocks {types}")
    if response.get("stop_reason") != "end_turn":
        problems.append(f"stop_reason {response.get('stop_reason')}")
    server_tools = (response.get("usage") or {}).get("server_tool_use") or {}
    if any(v for v in server_tools.values() if isinstance(v, (int, float))):
        problems.append(f"server tool use {server_tools}")
    if not str(response.get("model", "")).startswith(MODEL):
        problems.append(f"answered by {response.get('model')}")
    if problems:
        raise ClosedEnvironmentError("; ".join(problems))


# Scoring


class Scorer:
    """Embedding cosine similarity between the model's ending and the real ending."""

    def __init__(self) -> None:
        import sentence_transformers
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(EMBED_MODEL)
        self.version = sentence_transformers.__version__

    def score(self, pairs: list[tuple[str, str]]) -> list[float]:
        got = self.model.encode([g for g, _ in pairs], normalize_embeddings=True)
        want = self.model.encode([w for _, w in pairs], normalize_embeddings=True)
        return [round(float(a @ b), 3) for a, b in zip(got, want, strict=True)]


def strip_echo(prefix: str, completion: str) -> str:
    """Drop the shown part if the model repeated it before its ending."""
    text = completion.strip()
    if text.lower().startswith(prefix.lower()):
        text = text[len(prefix) :].strip()
    return text


# Run


def call(client, request: dict) -> dict:
    return client.messages.create(**request).model_dump(mode="json")


def summarize(rows: list[dict], selected: set[str]) -> str:
    lines = [
        "| Group | Mode | n | Mean | Median | Min | Max |",
        "|---|---|---|---|---|---|---|",
    ]
    for group in ("vals", "control"):
        for mode in PROMPTS:
            s = sorted(
                r["similarity"]
                for r in rows
                if r["group"] == group and r["mode"] == mode
            )
            if s:
                lines.append(
                    f"| {group} | {mode} | {len(s)} | {sum(s) / len(s):.2f} | {s[len(s) // 2]:.2f} | "
                    f"{s[0]:.2f} | {s[-1]:.2f} |"
                )
    by_id = {}
    for r in rows:
        by_id.setdefault(r["id"], {})[r["mode"]] = r["similarity"]
    pairs = [(i, m) for i, m in by_id.items() if "guided" in m and "general" in m]
    if pairs:
        higher = sum(m["guided"] > m["general"] for _, m in pairs)
        lines += ["", f"Guided above general on {higher} of {len(pairs)} questions."]
    top = sorted(
        (r for r in rows if r["group"] == "vals"), key=lambda r: -r["similarity"]
    )[:10]
    lines += [
        "",
        "Highest similarity, Vals questions (* = one of the 10 selected questions):",
        "",
    ]
    lines += [
        f"* {r['id']}{' *' if r['id'] in selected else ''} {r['mode']} {r['similarity']:.2f}: "
        f'real "{r["hidden"]}", model "{r["completion"]}"'
        for r in top
    ]
    return "\n".join(lines)


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
    ap.add_argument("--ids", help="comma separated ids to run, e.g. vals-07,ctrl-01")
    ap.add_argument(
        "--modes", default="guided,general", help="comma separated prompt modes"
    )
    ap.add_argument(
        "--cut", type=float, default=CUT, help="share of words shown, default 0.6"
    )
    ap.add_argument(
        "--vals-only", action="store_true", help="skip the control questions"
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="print prompts, call nothing"
    )
    ap.add_argument("--name", help="folder name under runs/ for a new run")
    args = ap.parse_args()

    include_control = CONTROL.exists() and not args.vals_only
    if not include_control and not (args.ids or args.vals_only):
        sys.exit(
            f"Missing {CONTROL.relative_to(ROOT)}. Add the control questions, or pass --vals-only."
        )
    items = load_questions(include_control)
    if args.ids:
        wanted = set(args.ids.split(","))
        items = [q for q in items if q["id"] in wanted]
        if missing := wanted - {q["id"] for q in items}:
            sys.exit(f"Unknown ids: {sorted(missing)}")
    modes = args.modes.split(",")
    with SELECTED.open(newline="", encoding="utf-8") as f:
        selected = {r["id"] for r in csv.DictReader(f)}

    if args.dry_run:
        for q in items:
            prefix, hidden = cut(q["question"], args.cut)
            print(f"{q['id']}\n  shown:  {prefix}\n  hidden: {hidden}")
        print(
            f"\n{len(items)} questions x {len(modes)} modes = {len(items) * len(modes)} requests"
        )
        return

    if not args.name:
        sys.exit("a new run requires --name (a role name, not a timestamp)")
    name = run_folder_name(args.name)

    import anthropic

    # Explicit key and URL, so nothing from the surrounding shell or app changes where calls go.
    client = anthropic.Anthropic(api_key=api_key(), base_url=API_URL)
    scorer = Scorer()
    run_dir = RUNS / name
    if run_dir.exists() and any(run_dir.iterdir()):
        sys.exit(f"{run_dir} already exists")
    (run_dir / "raw").mkdir(parents=True)

    rows, tokens_in, tokens_out = [], 0, 0
    for q in items:
        prefix, hidden = cut(q["question"], args.cut)
        for mode in modes:
            request = build_request(PROMPTS[mode].format(prefix=prefix))
            response = call(client, request)
            (run_dir / "raw" / f"{q['id']}__{mode}.json").write_text(
                json.dumps(
                    {"request": request, "response": response},
                    indent=2,
                    ensure_ascii=False,
                )
            )
            check_closed(request, response)
            completion = "".join(b["text"] for b in response["content"])
            usage = response["usage"]
            tokens_in += usage["input_tokens"]
            tokens_out += usage["output_tokens"]
            rows.append(
                {
                    "id": q["id"],
                    "group": q["group"],
                    "type": q["type"],
                    "mode": mode,
                    "selected": int(q["id"] in selected),
                    "shown": prefix,
                    "hidden": hidden,
                    "completion": strip_echo(prefix, completion),
                }
            )
            print(f"{q['id']:>8} {mode:<7} done", flush=True)

    sims = scorer.score([(r["completion"], r["hidden"]) for r in rows])
    for r, s in zip(rows, sims, strict=True):
        r["similarity"] = s

    with (run_dir / "results.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    cost = tokens_in / 1e6 * PRICE_IN + tokens_out / 1e6 * PRICE_OUT
    summary = (
        f"# Completion test run {name}\n\nModel `{MODEL}`, {len(rows)} requests, all passed the closed "
        f"environment checks. Shown: first {args.cut:.0%} of each question. Tokens: {tokens_in} in, {tokens_out} out. Cost about ${cost:.2f}.\n\n"
        f"Score: embedding cosine similarity, `{EMBED_MODEL}`, sentence-transformers {scorer.version}.\n\n"
        + summarize(rows, selected)
        + "\n"
    )
    (run_dir / "summary.md").write_text(summary)
    print("\n" + summary + f"\nSaved to {run_dir.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
