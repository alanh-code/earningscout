#!/usr/bin/env python3
"""Failure taxonomy for wrong answers across agent-loop baseline runs.

Eight root-cause categories, one primary per wrong answer. Each wrong answer
(post-policy results.csv, exclusions removed) gets an evidence digest built
from its saved trace, then two independent labels:
  pass_a  the judge model (JUDGE_MODEL), thinking on
  pass_b  the agent model (AGENT_MODEL), thinking on, a different checkpoint
Disagreements are settled by hand in taxonomy/resolutions.csv (id run primary secondary note).

  .venv/bin/python evals/baseline/agent_loop/failure_taxonomy.py label official repeat_2 repeat_3
  .venv/bin/python evals/baseline/agent_loop/failure_taxonomy.py report official repeat_2 repeat_3
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import llm

RUNS = HERE / "runs"
WORK = HERE / "taxonomy"
REPORT = HERE / "failure_taxonomy.md"
PASSES = {"pass_a": llm.JUDGE_MODEL, "pass_b": llm.AGENT_MODEL}


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


common = _load("baseline_common", ROOT / "evals" / "baseline" / "common.py")

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

LABEL_PROMPT = """You label why a finance research agent's answer was graded wrong.
Categories:
{cats}

Pick exactly one primary category (the root cause that, if fixed, would most likely make the answer right) and optionally one secondary. Base it only on the evidence. Reply with JSON only: {{"primary": "...", "secondary": "... or null", "why": "one sentence citing the specific figure, query, or URL"}}

Evidence:
{ev}
"""


def wrong_ids(run_dir: Path) -> list[str]:
    """Wrong answers in results.csv (after the verifier policy), excluded questions removed."""
    excluded = common.load_exclusions()
    with (run_dir / "results.csv").open(newline="", encoding="utf-8") as f:
        return [
            r["id"]
            for r in csv.DictReader(f)
            if r["overall"] == "wrong" and r["id"] not in excluded
        ]


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


def digest(trace: dict, max_result: int = 300) -> list[str]:
    lines: list[str] = []
    for t in trace.get("turns") or []:
        for c in t.get("tool_calls") or []:
            args = c.get("args") or {}
            status = (
                "refused" if c.get("refused") else ("ok" if c.get("ok") else "error")
            )
            if c["name"] == "web_search":
                lines.append(f"- search [{status}] {args.get('query', '')}")
                urls = re.findall(r'"url": "([^"]+)"', c.get("result") or "")
                lines += [f"    result {u}" for u in urls[:8]]
            elif c["name"] == "web_fetch":
                lines.append(
                    f"- fetch [{status}] {args.get('url', '')} ({c.get('page_chars', 0)} chars)"
                )
            else:
                code = (args.get("code") or "")[:500]
                out = (c.get("result") or "")[:max_result]
                lines.append(f"- code [{status}]\n```\n{code}\n```\n  output: {out}")
    return lines


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
        "Model answer:",
        a["model_answer"],
        "",
    ]
    tp = run_dir / "traces" / f"{qid}.json"
    if tp.exists():
        lines += ["Tool calls (in order):"] + digest(
            json.loads(tp.read_text(encoding="utf-8"))
        )
    return "\n".join(lines)


def parse_label(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {"primary": "parse_error", "secondary": None, "why": text[:200]}
    lab = json.loads(m.group(0))
    if lab.get("primary") not in CATEGORIES:
        lab["primary"] = f"invalid:{lab.get('primary')}"
    if lab.get("secondary") not in CATEGORIES:
        lab["secondary"] = None
    return lab


def label_one(model: str, ev: str) -> tuple[dict, float]:
    cats = "\n".join(f"- {k}: {v}" for k, v in CATEGORIES.items())
    out = llm.chat(
        model,
        [{"role": "user", "content": LABEL_PROMPT.format(cats=cats, ev=ev[:60000])}],
        max_tokens=16000,
        thinking=True,
    )
    return parse_label(llm.response_text(out["response"])), out["cost_usd"]


def cmd_label(runs: list[str], workers: int, cap: float) -> None:
    llm.require_off_peak(list(PASSES.values()))
    spent = 0.0
    for run in runs:
        run_dir = RUNS / run
        out_dir = WORK / run
        (out_dir / "evidence").mkdir(parents=True, exist_ok=True)
        ids = wrong_ids(run_dir)
        for qid in ids:
            (out_dir / "evidence" / f"{qid}.md").write_text(
                evidence(run_dir, qid), encoding="utf-8"
            )
        for pname, model in PASSES.items():
            path = out_dir / f"{pname}.json"
            done = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            todo = [q for q in ids if q not in done]
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futs = {
                    pool.submit(
                        label_one,
                        model,
                        (out_dir / "evidence" / f"{q}.md").read_text(encoding="utf-8"),
                    ): q
                    for q in todo
                }
                for fut in as_completed(futs):
                    q = futs[fut]
                    try:
                        lab, cost = fut.result()
                    except llm.PeakHours as exc:
                        path.write_text(
                            json.dumps(done, indent=1, ensure_ascii=False),
                            encoding="utf-8",
                        )
                        pool.shutdown(cancel_futures=True)
                        sys.exit(f"paused: {exc}")
                    done[q] = lab
                    spent += cost
                    path.write_text(
                        json.dumps(done, indent=1, ensure_ascii=False), encoding="utf-8"
                    )
                    if spent > cap:
                        pool.shutdown(cancel_futures=True)
                        sys.exit(f"label spend cap ${cap:.2f} reached")
            print(
                f"{run} {pname}: {len(done)}/{len(ids)} labeled, spend so far ${spent:.4f}",
                flush=True,
            )


def load_resolutions() -> dict:
    path = WORK / "resolutions.csv"
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        return {(r["run"], r["id"]): r for r in csv.DictReader(f)}


def final_labels(runs: list[str]) -> list[dict]:
    res = load_resolutions()
    rows = []
    for run in runs:
        out_dir = WORK / run
        a = json.loads((out_dir / "pass_a.json").read_text(encoding="utf-8"))
        b = json.loads((out_dir / "pass_b.json").read_text(encoding="utf-8"))
        for qid in wrong_ids(RUNS / run):
            la, lb = a.get(qid) or {}, b.get(qid) or {}
            r = res.get((run, qid))
            agree = la.get("primary") == lb.get("primary")
            if r:
                primary, secondary, note = (
                    r["primary"],
                    r.get("secondary") or None,
                    r.get("note") or "",
                )
            elif agree:
                primary, secondary, note = la.get("primary"), la.get("secondary"), ""
            else:
                primary, secondary, note = (
                    la.get("primary"),
                    la.get("secondary"),
                    "unresolved; pass_a kept",
                )
            rows.append(
                {
                    "run": run,
                    "id": qid,
                    "type": load_answer(RUNS / run, qid)["type"],
                    "pass_a": la.get("primary"),
                    "pass_b": lb.get("primary"),
                    "agree": agree,
                    "primary": primary,
                    "secondary": secondary,
                    "why": la.get("why", ""),
                    "note": note,
                }
            )
    return rows


def cmd_report(runs: list[str]) -> None:
    rows = final_labels(runs)
    WORK.mkdir(parents=True, exist_ok=True)
    with (WORK / "labels.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    n = len(rows)
    prim = Counter(r["primary"] for r in rows)
    sec = Counter(r["secondary"] for r in rows if r["secondary"])
    per_run = {
        run: Counter(r["primary"] for r in rows if r["run"] == run) for run in runs
    }
    agree = sum(r["agree"] for r in rows)
    lines = [
        "# Failure taxonomy: agent-loop baseline",
        "",
        f"Wrong answers after the verifier policy, exclusions removed, across runs {', '.join(runs)}: {n}.",
        (
            "Labels: two independent model passes "
            f"(pass_a `{PASSES['pass_a']}`, pass_b `{PASSES['pass_b']}`) on an evidence digest of the answer, failed checks and the saved tool trace; "
            "disagreements settled by hand against the evidence (`taxonomy/resolutions.csv`)."
        ),
        f"Pass agreement on primary cause: {agree}/{n} ({100 * agree / n:.0f}%).",
        "",
        "## Counts",
        "",
        "| Category | " + " | ".join(runs) + " | Total primary | Share | Secondary |",
        "|---|" + "---:|" * (len(runs) + 3),
    ]
    for cat in CATEGORIES:
        lines.append(
            f"| `{cat}` | "
            + " | ".join(str(per_run[r].get(cat, 0)) for r in runs)
            + f" | {prim.get(cat, 0)} | {100 * prim.get(cat, 0) / n:.0f}% | {sec.get(cat, 0)} |"
        )
    other = [k for k in prim if k not in CATEGORIES]
    for k in other:
        lines.append(
            f"| {k} | "
            + " | ".join(str(per_run[r].get(k, 0)) for r in runs)
            + f" | {prim[k]} | | |"
        )
    lines += [
        "",
        "## Per question",
        "",
        "| run | id | type | primary | secondary | pass_a | pass_b | why | note |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        why = (r["why"] or "").replace("|", "/").replace("\n", " ")
        lines.append(
            f"| {r['run']} | {r['id']} | {r['type']} | `{r['primary']}` | {('`' + r['secondary'] + '`') if r['secondary'] else ''} | "
            f"{r['pass_a']} | {r['pass_b']} | {why} | {r['note']} |"
        )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"{n} wrong answers labeled; agreement {agree}/{n}; wrote {REPORT.relative_to(ROOT)}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("step", choices=["label", "report"])
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--cap", type=float, default=2.0)
    args = ap.parse_args()
    if args.step == "label":
        cmd_label(args.runs, args.workers, args.cap)
    else:
        cmd_report(args.runs)


if __name__ == "__main__":
    main()
