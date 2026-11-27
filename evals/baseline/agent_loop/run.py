#!/usr/bin/env python3
"""Run Vals public questions with the agent loop in agent/, then grade with the 3-pass judge.

The agent (agent/llm.py AGENT_MODEL) calls three client-side tools: web_search
and web_fetch on Exa, and code_execution on an E2B sandbox. Gold hosts are
blocked in every tool. Grading uses the strict judge prompt and guide with the
judge model (JUDGE_MODEL), three passes, majority vote. The run folder is what
the verifier and apply_policy read.

  .venv/bin/python evals/baseline/agent_loop/run.py --name check --ids vals-01,vals-03
  .venv/bin/python evals/baseline/agent_loop/run.py --name official --workers 8 --spend-cap 10
  .venv/bin/python evals/baseline/agent_loop/run.py --resume --run-dir evals/baseline/agent_loop/runs/official
  .venv/bin/python evals/baseline/agent_loop/run.py --judge-only --run-dir evals/baseline/agent_loop/runs/official

A paid call never starts in provider peak hours (unless --allow-peak); the run
stops instead. --resume skips saved answers and saved judge passes.
  .venv/bin/python evals/baseline/agent_loop/run.py --report-only --run-dir evals/baseline/agent_loop/runs/official
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import llm, loop, tools
from agent.protocol import BLOCKED_DOMAINS, PROTOCOL_AS_OF, SEED, as_of_iso

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
JUDGE_DIR = ROOT / "evals" / "contamination" / "closed_book" / "judge"
JUDGE_PROMPT = JUDGE_DIR / "judge_prompt_strict.md"
JUDGE_GUIDE = (
    ROOT / "evals" / "contamination" / "closed_book" / "grading_guide_strict.md"
)
SPEND_CAP = 10.0


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Shared helpers: question loading, majority vote, judge CSVs, record files.
common = load_module("baseline_common", ROOT / "evals" / "baseline" / "common.py")
JUDGE_PASSES = common.JUDGE_PASSES
jr = load_module("closed_book_run_judge", JUDGE_DIR / "run_judge.py")


def set_judge_passes(n: int) -> None:
    """Judge passes for this run (3 for confirmation, 1 for cheap screening); majority of n."""
    global JUDGE_PASSES
    if n < 1:
        sys.exit("--judge-passes must be at least 1")
    JUDGE_PASSES = common.JUDGE_PASSES = n


def protocol_meta() -> dict:
    return {
        "harness": "agent_loop",
        "model": llm.AGENT_MODEL,
        "model_version": llm.model_config(llm.AGENT_MODEL).version,
        "judge_model": llm.JUDGE_MODEL,
        "judge_model_version": llm.model_config(llm.JUDGE_MODEL).version,
        "judge_prompt": str(JUDGE_PROMPT.relative_to(ROOT)),
        "judge_guide": str(JUDGE_GUIDE.relative_to(ROOT)),
        "judge_passes": JUDGE_PASSES,
        "seed": SEED,
        "thinking": f"enabled, reasoning_effort {loop.REASONING_EFFORT} (temperature does not apply)",
        "max_turns": loop.MAX_TURNS,
        "max_tokens_per_turn": loop.MAX_TOKENS,
        "tools": {
            "web_search": f"Exa /search type={tools.SEARCH_TYPE}, {tools.SEARCH_RESULTS} results, highlights, endPublishedDate={as_of_iso()}",
            "web_fetch": f"Exa /contents text up to {tools.FETCH_MAX_CHARS} chars, host check before and after",
            "code_execution": f"E2B code interpreter, internet off, {tools.EXEC_TIMEOUT_S}s per call, {tools.SANDBOX_LIFETIME_S}s lifetime, killed after each question",
        },
        "tool_budgets": tools.BUDGETS,
        "blocked_domains": list(BLOCKED_DOMAINS),
        "protocol_as_of": PROTOCOL_AS_OF,
    }


def agent_record(item: dict) -> dict:
    rec = loop.run_agent(item["question"])
    return {
        "id": item["id"],
        "type": item["type"],
        "question": item["question"],
        "answer": item["answer"],
        "rubric": item["rubric"],
        **rec,
        "error": None,
    }


def judge_one(
    item: dict, template: str, guide: str, pass_i: int
) -> tuple[dict, float, list[str]]:
    prompt = jr.build_prompt(item, template, guide)
    request = jr.build_request(llm.JUDGE_MODEL, prompt, seed=SEED + pass_i)
    cost = 0.0
    models: list[str] = []
    last_exc: Exception | None = None
    for _ in (1, 2):
        out = llm.send(request)
        cost += out["cost_usd"]
        models.append(out["reported_model"] or "")
        response = out["response"]
        try:
            if jr.is_truncated(response):
                raise ValueError("judge response truncated at max_tokens")
            parsed = jr.extract_json(jr.answer_text(response))
            jr.validate_grade(item, parsed)
            return parsed, cost, models
        except (ValueError, json.JSONDecodeError) as exc:
            last_exc = exc
    raise RuntimeError(f"judge failed for {item['id']}: {last_exc}")


def pass_path(run_dir: Path, pass_i: int, qid: str) -> Path:
    return run_dir / "judge" / "passes" / f"p{pass_i + 1}_{qid}.json"


def grade(
    records: list[dict], workers: int, spent: float, cap: float, run_dir: Path
) -> tuple[float, list[dict], list[str]]:
    """Judge every record JUDGE_PASSES times. Each finished grade is saved, so a rerun skips it."""
    template = JUDGE_PROMPT.read_text(encoding="utf-8")
    guide = JUDGE_GUIDE.read_text(encoding="utf-8")
    passes: list[dict] = [{} for _ in range(JUDGE_PASSES)]
    cost = 0.0
    models: set[str] = set()
    jobs = []
    for p in range(JUDGE_PASSES):
        for r in records:
            saved = pass_path(run_dir, p, r["id"])
            if saved.exists():
                data = json.loads(saved.read_text(encoding="utf-8"))
                passes[p][r["id"]] = data["grade"]
                cost += float(data.get("cost_usd") or 0)
                models.update(data.get("reported_models") or [])
            else:
                jobs.append((p, r))
    errors: list[str] = []
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {
            pool.submit(judge_one, r, template, guide, p): (p, r["id"]) for p, r in jobs
        }
        for fut in as_completed(futs):
            p, qid = futs[fut]
            try:
                parsed, c, ms = fut.result()
            except llm.PeakHours as exc:
                pool.shutdown(cancel_futures=True)
                raise SystemExit(f"paused: {exc}") from exc
            except Exception as exc:  # noqa: BLE001 - keep the other judge calls running
                errors.append(f"{qid} pass {p + 1}: {exc}")
                continue
            with lock:
                passes[p][qid] = parsed
                cost += c
                models.update(ms)
                common.write_json(
                    pass_path(run_dir, p, qid),
                    {"grade": parsed, "cost_usd": c, "reported_models": ms},
                )
            print(
                f"judge {qid} p{p + 1} {parsed['overall']}  ${c:.4f}  judge ${cost:.4f}",
                flush=True,
            )
            if spent + cost > cap:
                pool.shutdown(cancel_futures=True)
                raise RuntimeError(f"spend cap ${cap:.2f} reached during judging")
    if errors:
        raise RuntimeError(f"{len(errors)} judge calls failed; first: {errors[0]}")
    return cost, passes, sorted(models)


def write_summary(run_dir: Path, records: list[dict], meta: dict) -> None:
    exclusions = common.load_exclusions()
    scored = [r for r in records if r["id"] not in exclusions]
    labels = [r.get("overall") or "" for r in scored]
    counts = Counter(labels)
    n = len(scored)
    acc, lo, hi = common.bootstrap_ci(labels) if n else (0.0, 0.0, 0.0)
    agent_cost = sum(float(r.get("cost_usd") or 0) for r in records)
    judge_cost = float(meta.get("judge_cost_usd") or 0)
    lines = [
        f"# Agent-loop baseline {meta.get('name') or run_dir.name}",
        "",
        f"Agent `{meta['model']}` ({meta['model_version']}) in the tool loop from `agent/`, {len(records)} questions from `data/vals/public.csv`.",
        f"Judge: `{meta['judge_model']}`, `judge_prompt_strict.md`, {JUDGE_PASSES} passes, majority vote.",
        f'Protocol as-of date: {PROTOCOL_AS_OF}. It is injected into the system prompt when the question contains "current"; a date given in the question takes precedence.',
        f"Accuracy is scored on {n} questions; {len(records) - n} answered questions are excluded (`evals/baseline/excluded_questions.csv`).",
        f"Models reported by the API: agent {', '.join(meta.get('reported_agent_models') or [])}; judge {', '.join(meta.get('reported_judge_models') or [])}.",
        "",
        "## Tools",
        "",
        *[f"* `{k}`: {v}" for k, v in meta["tools"].items()],
        f"* Blocked hosts (search, fetch; the sandbox has no internet): {', '.join(meta['blocked_domains'])}",
        f"* Budgets per question: {json.dumps(meta['tool_budgets'])}; turn limit {meta['max_turns']}.",
        "",
        "## Accuracy",
        "",
        f"n={n}. Right {counts.get('right', 0)}, wrong {counts.get('wrong', 0)}, abstain {counts.get('abstain', 0)}.",
        f"Accuracy {100 * acc:.1f}% ({counts.get('right', 0)}/{n}), bootstrap 95% CI {100 * lo:.1f}–{100 * hi:.1f}%.",
        "",
        "## Cost and usage",
        "",
        f"Total cost about ${agent_cost + judge_cost:.4f} (agent ${agent_cost:.4f} including tools, judge ${judge_cost:.4f}).",
        "",
        "| id | type | overall | scored | agent USD | model USD | Exa USD | E2B USD | latency s | turns | tool calls | refused |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in records:
        tc = r.get("tool_cost_usd") or {}
        lines.append(
            f"| {r['id']} | {r['type']} | {r.get('overall') or ''} | {'no' if r['id'] in exclusions else 'yes'} | "
            f"${float(r.get('cost_usd') or 0):.4f} | ${float(r.get('model_cost_usd') or 0):.4f} | ${float(tc.get('exa') or 0):.4f} | "
            f"${float(tc.get('e2b') or 0):.4f} | {float(r.get('latency_s') or 0):.1f} | {r.get('n_turns') or 0} | "
            f"{r.get('n_tool_calls') or 0} | {r.get('n_refused') or 0} |"
        )
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def scored_items(items: list[dict], exclusions: dict[str, str]) -> list[dict]:
    """The default question set: every public question except the excluded ones."""
    return [q for q in items if q["id"] not in exclusions]


def load_answers(run_dir: Path) -> list[dict]:
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted((run_dir / "answers").glob("vals-*.json"))
    ]


def rewrite_summary(run_dir: Path) -> None:
    """Regenerate summary.md from the answers, results.csv and run_meta.json (used by apply_policy)."""
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
    records = {r["id"]: r for r in load_answers(run_dir)}
    with (run_dir / "results.csv").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["id"] in records:
                records[row["id"]]["overall"] = row.get("overall") or ""
    write_summary(run_dir, list(records.values()), meta)


def display_run_dir(run_dir: Path) -> str:
    """Repo-relative path for a run folder, even when --run-dir was relative."""
    path = Path(run_dir).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def finish(
    run_dir: Path, records: list[dict], meta: dict, workers: int, cap: float
) -> None:
    spent = sum(r["cost_usd"] for r in records)
    judge_cost, passes, judge_models = grade(records, workers, spent, cap, run_dir)
    common.write_judge_outputs(run_dir, records, passes, jr)
    meta.update(
        {
            "agent_cost_usd": spent,
            "judge_cost_usd": judge_cost,
            "total_cost_usd": spent + judge_cost,
            "reported_agent_models": sorted(
                {m for r in records for m in r.get("reported_models") or []}
            ),
            "reported_judge_models": judge_models,
            "n": len(records),
        }
    )
    common.write_json(run_dir / "run_meta.json", meta)
    write_summary(run_dir, records, meta)
    print(
        f"agent ${spent:.4f} + judge ${judge_cost:.4f} = ${spent + judge_cost:.4f}. Saved to {display_run_dir(run_dir)}",
        flush=True,
    )


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--name", help="folder name under runs/ (a role name, not a timestamp)"
    )
    ap.add_argument(
        "--ids",
        help="comma separated question ids (default: the scored set, all questions minus excluded_questions.csv)",
    )
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument(
        "--spend-cap",
        type=float,
        default=SPEND_CAP,
        help="stop scheduling new calls past this USD total; calls in flight still finish",
    )
    ap.add_argument(
        "--allow-peak", action="store_true", help="run even in provider peak hours"
    )
    ap.add_argument("--judge-only", action="store_true")
    ap.add_argument(
        "--resume",
        action="store_true",
        help="continue the run in --run-dir: skip saved answers and judge passes",
    )
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--run-dir", type=Path)
    ap.add_argument(
        "--judge-passes",
        type=int,
        help="judge passes (default 3; a resumed run keeps the count in its run_meta.json)",
    )
    args = ap.parse_args()
    saved_meta = (
        json.loads((args.run_dir / "run_meta.json").read_text(encoding="utf-8"))
        if args.run_dir and (args.run_dir / "run_meta.json").exists()
        else {}
    )
    set_judge_passes(args.judge_passes or saved_meta.get("judge_passes") or 3)

    if args.report_only:
        rewrite_summary(args.run_dir)
        return
    llm.ALLOW_PEAK = args.allow_peak
    llm.resolve_model(llm.AGENT_MODEL)
    llm.resolve_model(llm.JUDGE_MODEL)
    llm.require_off_peak([llm.AGENT_MODEL, llm.JUDGE_MODEL], args.allow_peak)

    if args.judge_only:
        run_dir = args.run_dir
        meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
        finish(run_dir, load_answers(run_dir), meta, args.workers, args.spend_cap)
        return

    all_items = common.load_questions()
    by_id = {q["id"]: q for q in all_items}
    if args.resume:
        if not args.run_dir:
            sys.exit("--resume requires --run-dir")
        run_dir = args.run_dir
        meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
        meta.pop("agent_failures", None)
        items = [by_id[i] for i in meta["ids"]]
    else:
        if not args.name:
            sys.exit("a new run requires --name (a role name, not a timestamp)")
        name = common.run_folder_name(args.name)
        items = scored_items(all_items, common.load_exclusions())
        if args.ids:
            wanted = args.ids.split(",")
            if missing := [i for i in wanted if i not in by_id]:
                sys.exit(f"unknown ids {missing}")
            items = [by_id[i] for i in wanted]
        run_dir = RUNS / name
        if run_dir.exists() and any(run_dir.iterdir()):
            sys.exit(
                f"{run_dir} already exists (use --resume --run-dir to continue it)"
            )
        meta = {
            "name": name,
            **protocol_meta(),
            "ids": [q["id"] for q in items],
            "workers": args.workers,
            "spend_cap_usd": args.spend_cap,
        }
    for sub in ("answers", "raw", "traces", "judge"):
        (run_dir / sub).mkdir(parents=True, exist_ok=True)
    common.write_json(run_dir / "run_meta.json", meta)

    records: list[dict] = [r for r in load_answers(run_dir) if r["id"] in meta["ids"]]
    done = {r["id"] for r in records}
    todo = [q for q in items if q["id"] not in done]
    spent = sum(float(r.get("cost_usd") or 0) for r in records)
    if done:
        print(
            f"resuming: {len(done)} answers saved, {len(todo)} to run, spent ${spent:.4f}",
            flush=True,
        )
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(agent_record, q): q["id"] for q in todo}
        for fut in as_completed(futs):
            qid = futs[fut]
            try:
                rec = fut.result()
            except (llm.OutOfCredit, llm.PeakHours) as exc:
                pool.shutdown(cancel_futures=True)
                sys.exit(f"{qid}: {exc}")
            except Exception as exc:  # noqa: BLE001 - record and keep going
                failures.append(f"{qid}: {type(exc).__name__}: {exc}")
                print(f"{qid} FAILED {exc}", flush=True)
                continue
            common.save_agent_record(run_dir, rec)
            records.append(rec)
            spent += rec["cost_usd"]
            print(
                f"{qid} done  ${rec['cost_usd']:.4f}  {rec['latency_s']:.0f}s  turns {rec['n_turns']}  "
                f"tools {rec['tool_calls']}  refused {rec['n_refused']}  spent ${spent:.4f}",
                flush=True,
            )
            if spent > args.spend_cap:
                pool.shutdown(cancel_futures=True)
                sys.exit(f"spend cap ${args.spend_cap:.2f} reached after agent answers")
    if failures:
        meta["agent_failures"] = failures
        common.write_json(run_dir / "run_meta.json", meta)
        sys.exit(f"{len(failures)} agent failures; first: {failures[0]}")
    order = {q["id"]: i for i, q in enumerate(items)}
    records.sort(key=lambda r: order[r["id"]])
    finish(run_dir, records, meta, args.workers, args.spend_cap)


if __name__ == "__main__":
    main()
