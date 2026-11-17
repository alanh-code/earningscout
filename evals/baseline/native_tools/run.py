#!/usr/bin/env python3
"""Run Vals public questions with Sonnet 5.5 native server tools, then grade with the strict Opus judge.

Pilot 5 questions first. If that finishes cleanly and the projected cost for all 50
(agent + 3-run Opus judge) is under $60, continue the remaining 45 and grade them.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import random
import re
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parents[3]
VALS = ROOT / "data" / "vals" / "public.csv"
EXCLUSIONS_PATH = ROOT / "evals" / "baseline" / "excluded_questions.csv"
RUNS = Path(__file__).resolve().parent / "runs"
JUDGE_PROMPT = (
    ROOT
    / "evals"
    / "contamination"
    / "closed_book"
    / "judge"
    / "judge_prompt_strict.md"
)
JUDGE_GUIDE = (
    ROOT / "evals" / "contamination" / "closed_book" / "grading_guide_strict.md"
)
# Scoring-protocol as-of date. After the newest gold as-of (April 7, 2025 in
# vals-07 and vals-19); in the month the public set appeared on GitHub; not a
# build or run day.
PROTOCOL_AS_OF = "Thursday, May 1, 2025"

AGENT_MODEL = "claude-sonnet-5-5"
JUDGE_MODEL = "claude-opus-5-5"
AGENT_MAX_TOKENS = 32000
JUDGE_MAX_TOKENS = 16384
JUDGE_PASSES = 3
SPEND_CAP = 60.0
PILOT_N = 5
# One question from each of five types, including two that say "currently".
PILOT_IDS = ["vals-01", "vals-03", "vals-08", "vals-12", "vals-33"]

# Latest dated server-tool types from the Anthropic tool reference.
# Domains that host the Vals finance-agent public gold (or obvious mirrors).
# A listed domain also covers its subdomains.
BLOCKED_DOMAINS = [
    "github.com",
    "githubusercontent.com",
    "raw.githubusercontent.com",
    "vals.ai",
    "huggingface.co",
    "hf.co",
    "zenodo.org",
    "hf-mirror.com",
]


def build_tools(*, block: bool) -> list[dict]:
    search: dict = {
        "type": "web_search_20260318",
        "name": "web_search",
        "max_uses": 15,
    }
    fetch: dict = {
        "type": "web_fetch_20260318",
        "name": "web_fetch",
        "max_uses": 15,
    }
    if block:
        search["blocked_domains"] = list(BLOCKED_DOMAINS)
        fetch["blocked_domains"] = list(BLOCKED_DOMAINS)
    return [
        search,
        fetch,
        {"type": "code_execution_20260521", "name": "code_execution"},
    ]


TOOLS = build_tools(block=True)


def configure_tools(*, block: bool) -> list[dict]:
    global TOOLS
    TOOLS = build_tools(block=block)
    return TOOLS


# USD per million tokens, plus $10 / 1000 web searches.
SONNET = {"input": 2.00, "output": 10.00, "cache_read": 0.10, "cache_write": 2.50}
OPUS = {"input": 4.00, "output": 20.00, "cache_read": 0.20, "cache_write": 5.00}
WEB_SEARCH_USD = 0.01
# Historical strict Opus judge cost on 15 short closed-book answers, 3 passes.
JUDGE_REF_PER_Q = 2.2941 / 15

SYSTEM_MINIMAL = "Answer the question. Use the available tools when they help."
SYSTEM_WITH_DATE = (
    "Answer the question. Use the available tools when they help. "
    f"Today's date is {PROTOCOL_AS_OF}. If the question gives a different as-of date, use the date in the question."
)


def api_key() -> str:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return value
    sys.exit("ANTHROPIC_API_KEY is not set in .env")


def load_judge():
    path = ROOT / "evals" / "contamination" / "closed_book" / "judge" / "run_judge.py"
    spec = importlib.util.spec_from_file_location("earningscout_run_judge", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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
    if len(items) != 50:
        sys.exit(f"expected 50 public questions, got {len(items)}")
    return items


def usage_cost(usage: dict | None, prices: dict) -> tuple[float, dict]:
    usage = usage or {}
    tokens_in = int(usage.get("input_tokens") or 0)
    tokens_out = int(usage.get("output_tokens") or 0)
    cache_read = int(usage.get("cache_read_input_tokens") or 0)
    cache_write = int(
        usage.get("cache_creation_input_tokens")
        or (usage.get("cache_creation") or {}).get("ephemeral_5m_input_tokens")
        or 0
    )
    searches = 0
    server = usage.get("server_tool_use") or {}
    if isinstance(server, dict):
        searches = int(server.get("web_search_requests") or 0)
    cost = (
        tokens_in / 1e6 * prices["input"]
        + tokens_out / 1e6 * prices["output"]
        + cache_read / 1e6 * prices["cache_read"]
        + cache_write / 1e6 * prices["cache_write"]
        + searches * WEB_SEARCH_USD
    )
    return cost, {
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
        "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": cache_write,
        "web_search_requests": searches,
    }


def add_usage(total: dict, part: dict) -> None:
    for k, v in part.items():
        total[k] = total.get(k, 0) + v


def stream_final(client, request: dict, retries: int = 6) -> dict:
    """Stream a Messages request and retry on rate limits."""
    delay = 2.0
    last_exc = None
    for attempt in range(retries):
        try:
            with client.messages.stream(**request) as stream:
                return stream.get_final_message().model_dump(mode="json")
        except anthropic.RateLimitError as exc:
            last_exc = exc
        except anthropic.APIStatusError as exc:
            if getattr(exc, "status_code", None) not in {429, 529}:
                raise
            last_exc = exc
        if attempt == retries - 1:
            break
        print(f"rate limit, retry {attempt + 1}/{retries} in {delay:.0f}s", flush=True)
        time.sleep(delay)
        delay = min(delay * 2, 60)
    raise last_exc


def answer_text(content: list) -> str:
    parts = []
    for block in content or []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text") or "")
    return "".join(parts).strip()


def count_tool_calls(content: list) -> dict:
    counts: dict[str, int] = Counter()
    for block in content or []:
        if not isinstance(block, dict):
            continue
        typ = block.get("type")
        name = block.get("name") or ""
        if typ in {"server_tool_use", "tool_use"}:
            counts["total"] += 1
            key = name or typ
            counts[key] += 1
    return dict(counts)


USAGE_LIMIT_TEXT = "reached your specified API usage limits"


def is_usage_limit(exc: BaseException) -> bool:
    return USAGE_LIMIT_TEXT in str(exc)


def system_for(question: str) -> str:
    if "current" in question.lower():
        return SYSTEM_WITH_DATE
    return SYSTEM_MINIMAL


def run_agent(client, item: dict) -> dict:
    started = time.perf_counter()
    messages = [{"role": "user", "content": item["question"]}]
    turns = []
    usage_tot = {}
    cost = 0.0
    tool_counts: Counter = Counter()
    stop_reason = None
    text = ""
    for _ in range(16):
        request = {
            "model": AGENT_MODEL,
            "max_tokens": AGENT_MAX_TOKENS,
            "system": system_for(item["question"]),
            "tools": TOOLS,
            "messages": messages,
        }
        response = stream_final(client, request)
        turns.append({"request_messages_len": len(messages), "response": response})
        part_cost, part_usage = usage_cost(response.get("usage"), SONNET)
        cost += part_cost
        add_usage(usage_tot, part_usage)
        content = response.get("content") or []
        tool_counts.update(count_tool_calls(content))
        stop_reason = response.get("stop_reason")
        text = answer_text(content)
        if stop_reason in {None, "end_turn", "stop_sequence"}:
            break
        if stop_reason == "pause_turn":
            messages = messages + [{"role": "assistant", "content": content}]
            continue
        if stop_reason == "max_tokens":
            raise RuntimeError("agent response truncated at max_tokens")
        if stop_reason == "tool_use":
            raise RuntimeError(
                "agent returned client tool_use; server tools should finish in-request"
            )
        raise RuntimeError(f"unexpected stop_reason {stop_reason!r}")
    else:
        raise RuntimeError("agent exceeded the turn limit")
    if not text:
        raise RuntimeError("agent returned no text answer")
    latency = time.perf_counter() - started
    return {
        "id": item["id"],
        "type": item["type"],
        "question": item["question"],
        "answer": item["answer"],
        "rubric": item["rubric"],
        "model_answer": text,
        "stop_reason": stop_reason,
        "tokens": usage_tot,
        "cost_usd": cost,
        "latency_s": latency,
        "tool_calls": dict(tool_counts),
        "n_tool_calls": int(tool_counts.get("total") or 0),
        "n_turns": len(turns),
        "error": None,
        "turns": turns,
    }


def judge_one(
    client, jr, template: str, guide: str, item: dict
) -> tuple[dict, float, dict]:
    prompt = jr.build_prompt(
        {
            "question": item["question"],
            "answer": item["answer"],
            "rubric": item["rubric"],
            "model_answer": item["model_answer"],
        },
        template,
        guide,
    )
    request = {
        "model": JUDGE_MODEL,
        "max_tokens": JUDGE_MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    }
    last_exc = None
    usage_tot = {}
    cost = 0.0
    response = {}
    for _ in (1, 2):
        response = stream_final(client, request)
        part_cost, part_usage = usage_cost(response.get("usage"), OPUS)
        cost += part_cost
        add_usage(usage_tot, part_usage)
        try:
            if jr.is_truncated(response):
                raise ValueError("judge response truncated at max_tokens")
            parsed = jr.extract_json(jr.answer_text(response))
            jr.validate_grade(
                {
                    "id": item["id"],
                    "question": item["question"],
                    "answer": item["answer"],
                    "rubric": item["rubric"],
                },
                parsed,
            )
            return parsed, cost, usage_tot
        except (ValueError, json.JSONDecodeError) as exc:
            last_exc = exc
    raise RuntimeError(f"judge failed for {item['id']}: {last_exc}")


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
    labels: list[str], n_boot: int = 10000, seed: int = 42
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


def project_total(agent_cost: float, n_done: int, avg_answer_chars: float) -> dict:
    if n_done == 0:
        return {"agent_50": 0.0, "judge_50": 0.0, "total_50": 0.0, "judge_scale": 1.0}
    agent_50 = agent_cost / n_done * 50
    scale = max(1.0, avg_answer_chars / 1500.0)
    scale = min(scale, 3.0)
    judge_50 = JUDGE_REF_PER_Q * 50 * scale
    return {
        "agent_50": agent_50,
        "judge_50": judge_50,
        "total_50": agent_50 + judge_50,
        "judge_scale": scale,
    }


def median(xs: list[float]) -> float:
    ys = sorted(xs)
    n = len(ys)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2:
        return ys[mid]
    return 0.5 * (ys[mid - 1] + ys[mid])


def write_summary(
    run_dir: Path,
    name: str,
    records: list[dict],
    judge_cost: float,
    enabled: dict,
    unavailable: list[str],
) -> None:
    exclusions = load_exclusions()
    scored = [r for r in records if r["id"] not in exclusions]
    excluded = [r for r in records if r["id"] in exclusions]
    labels = [r.get("overall") or "" for r in scored]
    n = len(scored)
    counts = Counter(labels)
    acc, lo, hi = bootstrap_ci(labels) if n else (0.0, 0.0, 0.0)
    agent_cost = sum(r.get("cost_usd") or 0 for r in records)
    total_cost = agent_cost + judge_cost
    latencies = [r["latency_s"] for r in records if r.get("latency_s") is not None]
    tool_avgs = [r.get("n_tool_calls") or 0 for r in records]
    excl_path = EXCLUSIONS_PATH.relative_to(ROOT)
    lines = [
        f"# Native-tools baseline {name}",
        "",
        f"Model `{AGENT_MODEL}` with built-in server tools, {len(records)} questions from `data/vals/public.csv`.",
        f"Judge: `{JUDGE_MODEL}`, `judge_prompt_strict.md`, {JUDGE_PASSES} passes, majority vote.",
        f'Protocol as-of date: {PROTOCOL_AS_OF}. It is injected into the system prompt when the question contains "current"; a date given in the question takes precedence.',
        f"Accuracy is scored on {n} questions after excluding {len(excluded)} listed in `{excl_path}`. Run data for excluded questions is kept.",
        "",
        "## Tools",
        "",
        f"Enabled: {json.dumps(enabled, ensure_ascii=False)}",
        f"Unavailable (not used): {'; '.join(unavailable)}",
        "",
        "## Accuracy",
        "",
        f"n={n}. Right {counts.get('right', 0)}, wrong {counts.get('wrong', 0)}, abstain {counts.get('abstain', 0)}.",
        f"Accuracy {100 * acc:.1f}% ({counts.get('right', 0)}/{n}), bootstrap 95% CI {100 * lo:.1f}–{100 * hi:.1f}%.",
        "",
        "By question type:",
        "",
        "| Type | n | Right | Wrong | Abstain | Accuracy |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    by_type: dict[str, list[str]] = {}
    for r in scored:
        by_type.setdefault(r["type"], []).append(r.get("overall") or "")
    for typ, labs in sorted(by_type.items()):
        c = Counter(labs)
        nt = len(labs)
        lines.append(
            f"| {typ} | {nt} | {c.get('right', 0)} | {c.get('wrong', 0)} | {c.get('abstain', 0)} | "
            f"{100 * c.get('right', 0) / nt:.1f}% |"
        )
    if excluded:
        lines += [
            "",
            "## Excluded questions",
            "",
            "These ids are kept in the run data and in the table below but are not scored.",
            "",
            "| id | type | overall | reason |",
            "|---|---|---|---|",
        ]
        for r in excluded:
            reason = exclusions.get(r["id"] or "", "")
            lines.append(
                f"| {r['id']} | {r['type']} | {r.get('overall') or ''} | {reason} |"
            )
    lines += [
        "",
        "## Cost and usage",
        "",
        f"Total cost about ${total_cost:.4f} (agent ${agent_cost:.4f}, judge ${judge_cost:.4f}).",
        f"Median latency {median(latencies):.1f}s. Average tool calls {sum(tool_avgs) / len(tool_avgs) if tool_avgs else 0:.2f}.",
        "",
        "| id | type | overall | scored | agent USD | latency s | tool calls | stop |",
        "|---|---|---|---|---:|---:|---:|---|",
    ]
    for r in records:
        scored_flag = "no" if r["id"] in exclusions else "yes"
        lines.append(
            f"| {r['id']} | {r['type']} | {r.get('overall') or ''} | {scored_flag} | ${r['cost_usd']:.4f} | "
            f"{r.get('latency_s') or 0:.1f} | {r.get('n_tool_calls') or 0} | {r.get('stop_reason') or ''} |"
        )
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def rewrite_summary(run_dir: Path) -> None:
    """Regenerate summary.md from saved results.csv and run_meta.json."""
    run_dir = Path(run_dir)
    meta_path = run_dir / "run_meta.json"
    meta = (
        json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    )
    records = []
    with (run_dir / "results.csv").open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            records.append(
                {
                    "id": r["id"],
                    "type": r["type"],
                    "overall": r.get("overall") or "",
                    "cost_usd": float(r["cost_usd"] or 0),
                    "latency_s": float(r["latency_s"] or 0),
                    "n_tool_calls": int(float(r.get("n_tool_calls") or 0)),
                    "stop_reason": r.get("stop_reason") or "",
                }
            )
    write_summary(
        run_dir,
        meta.get("name") or run_dir.name,
        records,
        float(meta.get("judge_cost_usd") or 0),
        meta.get("tools_enabled") or {},
        meta.get("tools_unavailable") or [],
    )


def main(
    name: str,
    spend_cap: float | None = None,
    workers: int = 8,
    no_pilot: bool = False,
    block_domains: bool = True,
) -> None:
    global SPEND_CAP
    if spend_cap is not None:
        SPEND_CAP = spend_cap
    configure_tools(block=block_domains)
    items = load_questions()
    by_id = {q["id"]: q for q in items}
    for qid in PILOT_IDS:
        if qid not in by_id:
            sys.exit(f"pilot id {qid} is not in the public set")
    rest_ids = [q["id"] for q in items if q["id"] not in PILOT_IDS]
    all_ids = [q["id"] for q in items]
    jr = load_judge()
    template = JUDGE_PROMPT.read_text(encoding="utf-8")
    guide = JUDGE_GUIDE.read_text(encoding="utf-8")
    client = anthropic.Anthropic(
        api_key=api_key(), base_url="https://api.anthropic.com", max_retries=5
    )

    run_dir = RUNS / name
    if run_dir.exists() and any(run_dir.iterdir()):
        sys.exit(f"{run_dir} already exists; use --resume --run-dir {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "raw").mkdir(exist_ok=True)
    (run_dir / "answers").mkdir(exist_ok=True)
    (run_dir / "judge").mkdir(exist_ok=True)
    (run_dir / "traces").mkdir(exist_ok=True)

    enabled = {
        "web_search": "web_search_20260318",
        "web_fetch": "web_fetch_20260318",
        "code_execution": "code_execution_20260521",
        "thinking": "adaptive (Sonnet 5.5 default, effort high)",
    }
    if block_domains:
        enabled["blocked_domains"] = list(BLOCKED_DOMAINS)
    unavailable = [
        "computer_toolset_20260801 and browser_toolset_20260801 (client tools; need a local executor)",
        "memory, bash, and text_editor (client tools)",
        "advisor_20260301 (beta; not a general research tool for this run)",
        "tool_search (for deferred tool loading; not needed here)",
    ]
    meta = {
        "name": name,
        "model": AGENT_MODEL,
        "judge_model": JUDGE_MODEL,
        "judge_prompt": "evals/contamination/closed_book/judge/judge_prompt_strict.md",
        "judge_guide": "evals/contamination/closed_book/grading_guide_strict.md",
        "tools_enabled": enabled,
        "tools_unavailable": unavailable,
        "pilot_ids": [] if no_pilot else PILOT_IDS,
        "spend_cap_usd": SPEND_CAP,
        "workers": workers,
        "protocol_as_of": PROTOCOL_AS_OF,
    }
    if block_domains:
        meta["blocked_domains"] = list(BLOCKED_DOMAINS)
    write_json(run_dir / "run_meta.json", meta)
    print(f"run folder {run_dir}", flush=True)
    print(f"enabled {enabled}", flush=True)
    print(f"unavailable: {unavailable}", flush=True)
    print(f"workers={workers}  spend cap ${SPEND_CAP:.2f}", flush=True)

    spent = 0.0
    records: list[dict] = []
    lock = threading.Lock()

    def run_ids(ids: list[str], label: str) -> None:
        nonlocal spent
        pending = list(ids)
        errors: list[str] = []

        def work(qid: str) -> dict:
            return run_agent(client, by_id[qid])

        print(f"{label} {len(pending)} questions, {workers} workers ...", flush=True)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(work, qid): qid for qid in pending}
            for fut in as_completed(futs):
                qid = futs[fut]
                try:
                    rec = fut.result()
                except Exception as exc:  # noqa: BLE001 — keep other questions running
                    errors.append(f"{qid}: {exc}")
                    print(f"{qid} ERROR: {exc}", flush=True)
                    continue
                with lock:
                    spent += rec["cost_usd"]
                    if spent > SPEND_CAP:
                        rec["error"] = (
                            f"exceeded spend cap ${SPEND_CAP:.2f} after this question"
                        )
                    save_agent_record(run_dir, rec)
                    records.append(rec)
                    print(
                        f"{qid} done  ${rec['cost_usd']:.4f}  {rec['latency_s']:.1f}s  "
                        f"tools={rec['n_tool_calls']}  running ${spent:.4f}",
                        flush=True,
                    )
        if errors:
            raise RuntimeError(f"{len(errors)} agent calls failed; first: {errors[0]}")
        if spent > SPEND_CAP:
            raise RuntimeError(f"exceeded spend cap ${SPEND_CAP:.2f}")

    try:
        if no_pilot:
            run_ids(all_ids, "full")
        else:
            run_ids(PILOT_IDS, "pilot")
            avg_chars = sum(len(r["model_answer"]) for r in records) / len(records)
            projection = project_total(spent, len(records), avg_chars)
            write_json(
                run_dir / "pilot_projection.json",
                {
                    "pilot_n": len(records),
                    "pilot_cost_usd": spent,
                    "avg_answer_chars": avg_chars,
                    **projection,
                },
            )
            print(
                f"pilot ok. agent ${spent:.4f} for {len(records)}. "
                f"projected 50: agent ${projection['agent_50']:.2f} + judge ${projection['judge_50']:.2f} "
                f"= ${projection['total_50']:.2f}",
                flush=True,
            )
            if projection["total_50"] > SPEND_CAP:
                print(
                    f"PILOT STOP: projected cost for all 50 exceeds ${SPEND_CAP:.2f}",
                    flush=True,
                )
                return
            run_ids(rest_ids, "full")
    except Exception as exc:
        write_json(
            run_dir / "run_stop.json",
            {"error": str(exc), "spent_usd": spent, "n": len(records)},
        )
        print(f"RUN STOP: {exc}", flush=True)
        raise

    records.sort(key=lambda r: r["id"])
    n = len(records)
    avg_chars = sum(len(r["model_answer"] or "") for r in records) / n
    judge_est = JUDGE_REF_PER_Q * n * min(3.0, max(1.0, avg_chars / 1500.0))
    if spent + judge_est > SPEND_CAP:
        print(
            f"STOP before judge: agent ${spent:.4f} + estimated judge ${judge_est:.2f} would exceed ${SPEND_CAP:.2f}",
            flush=True,
        )
        write_summary(run_dir, name, records, 0.0, enabled, unavailable)
        return

    print(f"grading {n} answers, 3 passes, {workers} workers ...", flush=True)
    judge_cost, pass_parses = grade_records_parallel(
        client, jr, template, guide, records, workers, spent
    )
    write_judge_outputs(run_dir, records, pass_parses, jr)
    write_summary(run_dir, name, records, judge_cost, enabled, unavailable)
    meta.update(
        {
            "agent_cost_usd": spent,
            "judge_cost_usd": judge_cost,
            "total_cost_usd": spent + judge_cost,
            "n": n,
            "judge_workers": workers,
        }
    )
    write_json(run_dir / "run_meta.json", meta)
    exclusions = load_exclusions()
    scored = [r for r in records if r["id"] not in exclusions]
    acc, lo, hi = (
        bootstrap_ci([r["overall"] for r in scored]) if scored else (0.0, 0.0, 0.0)
    )
    counts = Counter(r["overall"] for r in scored)
    print(
        f"\nDone. {counts.get('right', 0)} right, {counts.get('wrong', 0)} wrong, {counts.get('abstain', 0)} abstain "
        f"on {len(scored)} scored questions. "
        f"Accuracy {100 * acc:.1f}% (95% CI {100 * lo:.1f}–{100 * hi:.1f}%). "
        f"Cost ${spent + judge_cost:.4f}. Saved to {run_dir}",
        flush=True,
    )


def load_saved_records(run_dir: Path) -> list[dict]:
    answers = sorted((run_dir / "answers").glob("vals-*.json"))
    records = []
    for path in answers:
        rec = json.loads(path.read_text(encoding="utf-8"))
        if rec.get("error") or not rec.get("model_answer"):
            raise RuntimeError(f"{path.name} is missing a model answer")
        records.append(rec)
    records.sort(key=lambda r: r["id"])
    if len(records) != 50:
        raise RuntimeError(f"expected 50 answers, found {len(records)}")
    return records


def grade_records_parallel(
    client,
    jr,
    template: str,
    guide: str,
    records: list[dict],
    workers: int,
    spend: float,
) -> tuple[float, list[dict]]:
    jobs = []
    for pass_i in range(JUDGE_PASSES):
        for rec in records:
            jobs.append((pass_i, rec))

    pass_parses: list[dict[str, dict]] = [{} for _ in range(JUDGE_PASSES)]
    judge_cost = 0.0
    errors = []

    def work(job):
        pass_i, rec = job
        parsed, cost, _usage = judge_one(client, jr, template, guide, rec)
        return pass_i, rec["id"], parsed, cost

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(work, job) for job in jobs]
        done_n = 0
        for fut in as_completed(futs):
            try:
                pass_i, qid, parsed, cost = fut.result()
            except Exception as exc:  # noqa: BLE001 — keep other judge calls running
                errors.append(str(exc))
                print(f"judge error: {exc}", flush=True)
                continue
            judge_cost += cost
            pass_parses[pass_i][qid] = parsed
            done_n += 1
            if done_n == 1 or done_n % 10 == 0 or done_n == len(jobs):
                print(
                    f"judge {done_n}/{len(jobs)}  last {qid} p{pass_i + 1} {parsed['overall']}  "
                    f"${cost:.4f}  judge ${judge_cost:.4f}",
                    flush=True,
                )
            if spend + judge_cost > SPEND_CAP:
                raise RuntimeError(
                    f"spend cap reached during judge at ${spend + judge_cost:.4f}"
                )
    if errors:
        raise RuntimeError(f"{len(errors)} judge calls failed; first: {errors[0]}")
    missing = [
        f"{rec['id']} pass {i + 1}"
        for i in range(JUDGE_PASSES)
        for rec in records
        if rec["id"] not in pass_parses[i]
    ]
    if missing:
        raise RuntimeError(f"missing judge results: {missing[:8]}")
    return judge_cost, pass_parses


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


def run_judge_only(run_dir: Path, workers: int) -> None:
    jr = load_judge()
    template = JUDGE_PROMPT.read_text(encoding="utf-8")
    guide = JUDGE_GUIDE.read_text(encoding="utf-8")
    client = anthropic.Anthropic(
        api_key=api_key(), base_url="https://api.anthropic.com"
    )
    records = load_saved_records(run_dir)
    meta_path = run_dir / "run_meta.json"
    meta = (
        json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    )
    enabled = meta.get("tools_enabled") or {}
    unavailable = meta.get("tools_unavailable") or []
    name = meta.get("name") or run_dir.name
    spent = float(sum(r.get("cost_usd") or 0 for r in records))
    print(
        f"judge-only {len(records)} answers, {workers} workers, agent already ${spent:.4f}",
        flush=True,
    )
    judge_cost, pass_parses = grade_records_parallel(
        client, jr, template, guide, records, workers, spent
    )
    write_judge_outputs(run_dir, records, pass_parses, jr)
    write_summary(run_dir, name, records, judge_cost, enabled, unavailable)
    meta.update(
        {
            "agent_cost_usd": spent,
            "judge_cost_usd": judge_cost,
            "total_cost_usd": spent + judge_cost,
            "n": len(records),
            "judge_workers": workers,
        }
    )
    write_json(meta_path, meta)
    acc, lo, hi = bootstrap_ci([r["overall"] for r in records])
    counts = Counter(r["overall"] for r in records)
    print(
        f"\nDone. {counts.get('right', 0)} right, {counts.get('wrong', 0)} wrong, {counts.get('abstain', 0)} abstain. "
        f"Accuracy {100 * acc:.1f}% (95% CI {100 * lo:.1f}–{100 * hi:.1f}%). "
        f"Cost ${spent + judge_cost:.4f}. Saved to {run_dir}",
        flush=True,
    )


def resume_run(run_dir: Path, workers: int) -> None:
    """Finish missing answers in an existing run folder, then grade all 50."""
    run_dir = Path(run_dir)
    if not (run_dir / "answers").is_dir():
        sys.exit(f"no answers folder in {run_dir}")
    items = {q["id"]: q for q in load_questions()}
    existing: dict[str, dict] = {}
    for path in (run_dir / "answers").glob("vals-*.json"):
        rec = json.loads(path.read_text(encoding="utf-8"))
        if rec.get("model_answer") and not rec.get("error"):
            existing[rec["id"]] = rec
    missing = [f"vals-{i:02d}" for i in range(1, 51) if f"vals-{i:02d}" not in existing]
    spent = float(sum(r.get("cost_usd") or 0 for r in existing.values()))
    print(
        f"resume {run_dir}: {len(existing)} saved, {len(missing)} remaining, "
        f"agent already ${spent:.4f}, cap ${SPEND_CAP:.2f}, workers={workers}",
        flush=True,
    )
    (run_dir / "raw").mkdir(exist_ok=True)
    (run_dir / "traces").mkdir(exist_ok=True)
    (run_dir / "judge").mkdir(exist_ok=True)
    client = anthropic.Anthropic(
        api_key=api_key(), base_url="https://api.anthropic.com", max_retries=5
    )
    meta_path = run_dir / "run_meta.json"
    prior_meta = (
        json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    )
    prior_block = bool(
        prior_meta.get("blocked_domains")
        or (prior_meta.get("tools_enabled") or {}).get("blocked_domains")
    )
    configure_tools(block=prior_block)
    records = list(existing.values())
    lock = threading.Lock()
    errors: list[str] = []

    def work(qid: str) -> dict:
        return run_agent(client, items[qid])

    if missing:
        if spent >= SPEND_CAP:
            raise RuntimeError(
                f"spend cap ${SPEND_CAP:.2f} already reached before resume"
            )
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(work, qid): qid for qid in missing}
            for fut in as_completed(futs):
                qid = futs[fut]
                try:
                    rec = fut.result()
                except Exception as exc:
                    msg = f"{qid}: {exc}"
                    errors.append(msg)
                    print(f"{qid} ERROR: {exc}", flush=True)
                    if is_usage_limit(exc):
                        for other in futs:
                            other.cancel()
                        raise RuntimeError(
                            f"API usage limit hit on {qid}; stopping immediately."
                        ) from exc
                    continue
                with lock:
                    spent += rec["cost_usd"]
                    if spent > SPEND_CAP:
                        rec["error"] = (
                            f"exceeded spend cap ${SPEND_CAP:.2f} after this question"
                        )
                    save_agent_record(run_dir, rec)
                    records.append(rec)
                    print(
                        f"{qid} done  ${rec['cost_usd']:.4f}  {rec['latency_s']:.1f}s  "
                        f"tools={rec['n_tool_calls']}  running ${spent:.4f}",
                        flush=True,
                    )
                    if spent > SPEND_CAP:
                        for other in futs:
                            other.cancel()
                        raise RuntimeError(f"exceeded spend cap ${SPEND_CAP:.2f}")
        if errors:
            raise RuntimeError(f"{len(errors)} agent calls failed; first: {errors[0]}")

    have = {r["id"] for r in records}
    if len(have) != 50:
        missing_now = [
            f"vals-{i:02d}" for i in range(1, 51) if f"vals-{i:02d}" not in have
        ]
        raise RuntimeError(f"still missing {missing_now}")

    run_judge_only(run_dir, workers)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--judge-only", action="store_true")
    ap.add_argument(
        "--report-only",
        action="store_true",
        help="regenerate summary.md from saved results, applying excluded_questions.csv",
    )
    ap.add_argument("--run-dir", type=Path)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument(
        "--spend-cap",
        type=float,
        default=None,
        help="override the default spend cap (USD, agent+judge)",
    )
    ap.add_argument(
        "--no-pilot",
        action="store_true",
        help="run all 50 questions in parallel without a 5-question pilot",
    )
    ap.add_argument(
        "--resume",
        action="store_true",
        help="finish missing answers in --run-dir, then grade all 50",
    )
    ap.add_argument(
        "--name",
        help="folder name under runs/ for a new run (required unless resuming or reporting)",
    )
    ap.add_argument(
        "--no-blocked-domains",
        action="store_true",
        help="do not block gold-host domains on web search and fetch (first-run setting)",
    )
    args = ap.parse_args()
    if args.spend_cap is not None:
        globals()["SPEND_CAP"] = args.spend_cap
    modes = sum([args.judge_only, args.report_only, args.resume])
    if modes > 1:
        sys.exit("use only one of --judge-only, --report-only, or --resume")
    if args.resume:
        if not args.run_dir:
            sys.exit("--resume requires --run-dir")
        resume_run(args.run_dir, args.workers)
    elif args.report_only:
        if not args.run_dir:
            sys.exit("--report-only requires --run-dir")
        rewrite_summary(args.run_dir)
        print(f"wrote {Path(args.run_dir) / 'summary.md'}")
    elif args.judge_only:
        if not args.run_dir:
            sys.exit("--judge-only requires --run-dir")
        run_judge_only(args.run_dir, args.workers)
    else:
        if not args.name:
            sys.exit("a new run requires --name (a role name, not a timestamp)")
        main(
            name=run_folder_name(args.name),
            spend_cap=args.spend_cap,
            workers=args.workers,
            no_pilot=args.no_pilot,
            block_domains=not args.no_blocked_domains,
        )
