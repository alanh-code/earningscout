#!/usr/bin/env python3
"""Failure taxonomy for wrong answers in a native-tools baseline run.

Steps (each re-runnable; earlier outputs are reused, not overwritten):
  trace   Replay each currently-wrong question once with the same agent setup and save
          the full tool trace (the original run kept only final answers).
  label   Independent second-pass labels from a cheap Claude call that sees only the
          evidence digest and the category definitions.
  report  Merge hand labels, second-pass labels and the current wrong set into
          failure_taxonomy.md.

The wrong set is read from <run>/results.csv each time, so re-running after a grade
change picks up new or removed wrong answers; ids without a hand label are listed as
"unlabeled" in the report.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
WORK = HERE / "taxonomy"  # traces, evidence, labels.csv, second_pass.json, notes.md
REPORT = HERE / "failure_taxonomy.md"
EXCLUDED_CSV = HERE.parent / "excluded_questions.csv"
LABEL_MODEL = "claude-sonnet-5-5"
LABEL_PRICES = {"input": 2.00, "output": 10.00}

# Derived from the wrong set of the first unrestricted run (see failure_taxonomy.md).
CATEGORIES = {
    "shallow_retrieval": "A required item was never retrieved: the agent stopped at search snippets or one secondary page and did not open the filing section that holds it.",
    "omitted_item": "The needed figure or point was in the retrieved material (or computable from it) but was left out of the answer.",
    "interpretation_choice": "The question is open to more than one reading; the agent picked a different, stated definition, assumption, or scope than the gold (cash-flow basis, tax treatment, peer set, risk scope).",
    "guidance_benchmark": "Beat/miss measured against a different guidance reference than the gold (low end vs midpoint, margin range vs dollar guide, final vs initial range).",
    "later_data": "Used data newer than the time frame the question implies (post-close status, later raised guidance, latest releases), so time-bound gold points are missed.",
    "unsourced_figure": "A precise number came from memory or rounded inputs rather than the filing, so it is close but not exact.",
    "misread_source": "Reached a source with the answer but misread or misdescribed a figure or item.",
    "gold_issue": "The model answer is defensible and the gold is the problem (inputs rounded differently, narrower than the question, or ambiguous).",
}


def default_run() -> Path:
    """The taxonomy was built on the first-run grades."""
    path = RUNS / "first-run"
    if not (path / "results.csv").exists():
        raise SystemExit(f"default run not found: {path}")
    return path


def load_excluded() -> dict:
    if not EXCLUDED_CSV.exists():
        return {}
    with EXCLUDED_CSV.open(newline="", encoding="utf-8") as f:
        return {r["id"]: r["reason"] for r in csv.DictReader(f)}


EXCLUDED = load_excluded()


def load_run_module():
    spec = importlib.util.spec_from_file_location("native_tools_run", HERE / "run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def wrong_ids(run_dir: Path, include_excluded: bool = False) -> list[str]:
    with (run_dir / "results.csv").open(newline="", encoding="utf-8") as f:
        ids = [r["id"] for r in csv.DictReader(f) if r["overall"] == "wrong"]
    return ids if include_excluded else [q for q in ids if q not in EXCLUDED]


def load_answer(run_dir: Path, qid: str) -> dict:
    return json.loads((run_dir / "answers" / f"{qid}.json").read_text(encoding="utf-8"))


def failed_checks(run_dir: Path, qid: str) -> list[str]:
    out = []
    with (run_dir / "judge" / "judge_grades_majority.csv").open(
        newline="", encoding="utf-8"
    ) as f:
        for r in csv.DictReader(f):
            if r["question_id"] != qid:
                continue
            bad = (r["operator"] == "correctness" and r["result"] != "met") or (
                r["operator"] == "contradiction" and r["result"] == "triggered"
            )
            if bad:
                out.append(f"[{r['operator']} {r['result']}] {r['criteria']}")
    return out


# ---------- trace ----------


def cmd_trace(run_dir: Path, cap: float, workers: int, ids: list[str] | None) -> None:
    rm = load_run_module()
    import anthropic

    client = anthropic.Anthropic(api_key=rm.api_key(), max_retries=4)
    out_dir = WORK / "traces"
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = [
        q
        for q in (ids or wrong_ids(run_dir, include_excluded=True))
        if not (out_dir / f"{q}.json").exists()
    ]
    spent = 0.0

    def work(qid: str):
        a = load_answer(run_dir, qid)
        item = {k: a[k] for k in ("id", "type", "question", "answer", "rubric")}
        try:
            rec = rm.run_agent(client, item)
        except Exception as exc:  # noqa: BLE001 — keep other questions running
            return qid, 0.0, str(exc)
        (out_dir / f"{qid}.json").write_text(
            json.dumps(rec, indent=1, ensure_ascii=False, default=str), encoding="utf-8"
        )
        return qid, rec["cost_usd"], None

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for qid, cost, err in ex.map(work, todo):
            spent += cost
            print(
                f"{qid} cost=${cost:.3f} total=${spent:.2f}"
                + (f" ERROR {err}" if err else ""),
                flush=True,
            )
            if spent > cap:
                print("trace cap reached; remaining jobs still finish", flush=True)
    print(f"trace spend ${spent:.2f}")


def digest_trace(rec: dict, max_code: int = 400, max_out: int = 700) -> dict:
    searches, fetches, code, outputs, result_urls, cites = [], [], [], [], [], []
    for turn in rec.get("turns", []):
        for b in turn["response"].get("content") or []:
            t = b.get("type")
            if t == "server_tool_use":
                inp = b.get("input") or {}
                if b.get("name") == "web_search":
                    searches.append(inp.get("query", ""))
                elif b.get("name") == "web_fetch":
                    fetches.append(inp.get("url", ""))
                else:
                    code.append(
                        (inp.get("code") or inp.get("command") or json.dumps(inp))[
                            :max_code
                        ]
                    )
            elif t == "web_search_tool_result":
                for r in b.get("content") or []:
                    if (
                        isinstance(r, dict)
                        and r.get("url")
                        and r["url"] not in result_urls
                    ):
                        result_urls.append(r["url"])
            elif t == "web_fetch_tool_result":
                c = b.get("content") or {}
                if isinstance(c, dict) and str(c.get("type", "")).endswith("error"):
                    fetches.append(f"  -> fetch error {c.get('error_code')}")
            elif t == "code_execution_tool_result":
                c = b.get("content") or {}
                out = (c.get("stdout") or "").strip() if isinstance(c, dict) else ""
                if out:
                    outputs.append(out[:max_out])
            elif t == "text":
                for ci in b.get("citations") or []:
                    u = ci.get("url")
                    if u and u not in cites:
                        cites.append(u)
    return {
        "searches": searches,
        "fetches": fetches,
        "code": code,
        "outputs": outputs,
        "result_urls": result_urls,
        "citations": cites,
        "replay_answer": rec.get("model_answer", ""),
    }


def evidence(run_dir: Path, qid: str) -> str:
    a = load_answer(run_dir, qid)
    lines = [
        f"# {qid} ({a['type']})",
        "",
        f"Question: {a['question']}",
        "",
        "Gold answer:",
        a["answer"],
        "",
        "Failed rubric checks (judge majority):",
    ]
    lines += [f"- {c}" for c in failed_checks(run_dir, qid)] or ["- (none listed)"]
    lines += [
        "",
        f"Judge reason: {a.get('judge_reason', '')}",
        "",
        f"Original model answer (tool calls {a.get('tool_calls')}):",
        a["model_answer"],
        "",
    ]
    tp = WORK / "traces" / f"{qid}.json"
    if tp.exists():
        d = digest_trace(json.loads(tp.read_text(encoding="utf-8")))
        lines += (
            [
                "Replay trace (same setup, separate run; original trace was not saved):",
                "Searches:",
            ]
            + [f"- {s}" for s in d["searches"]]
            + ["Fetches:"]
            + [f"- {u}" for u in d["fetches"]]
        )
        lines += ["Search result URLs (first 20):"] + [
            f"- {u}" for u in d["result_urls"][:20]
        ]
        lines += ["Cited URLs:"] + [f"- {u}" for u in d["citations"][:15]]
        lines += ["Code (truncated):"] + [f"```\n{c}\n```" for c in d["code"][:4]]
        lines += [
            "Code output excerpts (plaintext only; some outputs are encrypted):"
        ] + [f"```\n{o}\n```" for o in d["outputs"][:8]]
        lines += ["Replay answer:", d["replay_answer"], ""]
    else:
        lines += ["Replay trace: not available", ""]
    return "\n".join(lines)


def cmd_evidence(run_dir: Path) -> None:
    out = WORK / "evidence"
    out.mkdir(parents=True, exist_ok=True)
    for qid in wrong_ids(run_dir):
        (out / f"{qid}.md").write_text(evidence(run_dir, qid), encoding="utf-8")
    print(f"wrote evidence for {len(wrong_ids(run_dir))} ids to {out}")


# ---------- second-pass label ----------

LABEL_PROMPT = """You label why a finance research agent's answer was graded wrong.
Categories:
{cats}

Pick exactly one primary category (the root cause that, if fixed, would most likely make the answer right) and optionally one secondary. Base it only on the evidence. Reply with JSON only: {{"primary": "...", "secondary": "... or null", "why": "one sentence citing the specific figure, query, or URL"}}

Evidence:
{ev}
"""


def cmd_label(run_dir: Path, cap: float, workers: int) -> None:
    rm = load_run_module()
    import anthropic

    client = anthropic.Anthropic(api_key=rm.api_key(), max_retries=4)
    out = WORK / "second_pass.json"
    done = json.loads(out.read_text()) if out.exists() else {}
    cats = "\n".join(f"- {k}: {v}" for k, v in CATEGORIES.items())
    todo = [q for q in wrong_ids(run_dir) if q not in done]

    def work(qid):
        msg = client.messages.create(
            model=LABEL_MODEL,
            max_tokens=2000,
            messages=[
                {
                    "role": "user",
                    "content": LABEL_PROMPT.format(
                        cats=cats, ev=evidence(run_dir, qid)[:60000]
                    ),
                }
            ],
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        m = re.search(r"\{.*\}", text, re.DOTALL)
        cost = (
            msg.usage.input_tokens / 1e6 * LABEL_PRICES["input"]
            + msg.usage.output_tokens / 1e6 * LABEL_PRICES["output"]
        )
        return (
            qid,
            (
                json.loads(m.group(0))
                if m
                else {"primary": "parse_error", "why": text[:200]}
            ),
            cost,
        )

    spent = 0.0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for qid, lab, cost in ex.map(work, todo):
            done[qid] = lab
            spent += cost
            if spent > cap:
                break
    out.write_text(json.dumps(done, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"labeled {len(todo)} ids, spend ${spent:.3f}")


# ---------- report ----------


def read_hand(path: Path) -> dict:
    with path.open(newline="", encoding="utf-8") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def cmd_report(run_dir: Path, hand_path: Path) -> None:
    ids = wrong_ids(run_dir)
    hand = read_hand(hand_path)
    sp_path = WORK / "second_pass.json"
    second = json.loads(sp_path.read_text()) if sp_path.exists() else {}
    types = {q: load_answer(run_dir, q)["type"] for q in ids}
    labeled = [q for q in ids if q in hand]
    counts = Counter(hand[q]["primary"] for q in labeled)
    sec_counts = Counter(
        hand[q]["secondary"] for q in labeled if hand[q].get("secondary")
    )
    agree = [
        q
        for q in labeled
        if q in second and second[q].get("primary") == hand[q]["first_pass"]
    ]
    compared = [q for q in labeled if q in second]

    L = [
        "# Failure taxonomy: native-tools baseline",
        "",
        f"Grades: `runs/{run_dir.name}`.",
        f"Wrong answers in scope: {len(ids)} (from `results.csv`, exclusions removed). Labeled: {len(labeled)}.",
    ]
    excl = [q for q in wrong_ids(run_dir, include_excluded=True) if q in EXCLUDED]
    if excl:
        L.append(
            f"Excluded from scoring and counts: {', '.join(excl)} ({EXCLUDED[excl[0]]})."
        )
    stale = sorted(set(hand) - set(ids) - set(EXCLUDED))
    missing = [q for q in ids if q not in hand]
    if missing:
        L.append(f"Unlabeled (newly wrong): {', '.join(missing)}.")
    if stale:
        L.append(f"Labeled but no longer wrong (excluded): {', '.join(stale)}.")
    L += [
        "",
        (
            "Evidence comes from the original answer, the judge's failed checks, and one replay per question "
            "with the same setup (the original run saved no tool traces). Replays are a separate sample, so they "
            "show search behavior, not the exact original path."
        ),
        "",
        "## Categories",
        "",
        "| Category | Definition | Primary | Secondary |",
        "|---|---|---:|---:|",
    ]
    for k, v in CATEGORIES.items():
        L.append(f"| `{k}` | {v} | {counts.get(k, 0)} | {sec_counts.get(k, 0)} |")
    if compared:
        L += [
            "",
            (
                f"Two-pass agreement on primary cause (hand first pass vs independent model pass): "
                f"{len(agree)}/{len(compared)} ({100 * len(agree) / len(compared):.0f}%). "
                "Disagreements were re-read against the trace and settled by hand; see the resolution column."
            ),
        ]
    L += [
        "",
        "## Per question",
        "",
        "| id | type | primary | secondary | evidence | second pass | resolution |",
        "|---|---|---|---|---|---|---|",
    ]
    for q in labeled:
        h = hand[q]
        s = second.get(q, {}).get("primary", "")
        L.append(
            f"| {q} | {types[q]} | `{h['primary']}` | {('`' + h['secondary'] + '`') if h.get('secondary') else ''} | "
            f"{h['evidence']} | {s} | {h.get('resolution', '')} |"
        )
    notes = WORK / "notes.md"
    if notes.exists():
        L += ["", notes.read_text(encoding="utf-8").strip()]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("step", choices=["trace", "evidence", "label", "report"])
    p.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="graded run to read (default: runs/first-run)",
    )
    p.add_argument(
        "--labels",
        type=Path,
        default=None,
        help="hand labels CSV (default taxonomy/labels.csv)",
    )
    p.add_argument(
        "--cap", type=float, default=7.0, help="spend cap in USD for this step"
    )
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--ids", nargs="*")
    a = p.parse_args()
    run_dir = (a.run_dir or default_run()).resolve()
    print(f"grades from {run_dir.name}")
    if a.step == "trace":
        cmd_trace(run_dir, a.cap, a.workers, a.ids)
    elif a.step == "evidence":
        cmd_evidence(run_dir)
    elif a.step == "label":
        cmd_label(run_dir, a.cap, a.workers)
    else:
        cmd_report(run_dir, a.labels or WORK / "labels.csv")


if __name__ == "__main__":
    main()
