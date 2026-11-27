"""Accuracy and stability of a candidate configuration against a baseline, from existing runs.

  .venv/bin/python evals/stability/ablate.py --base RUN RUN RUN --cand RUN RUN RUN [--subset informative|ID,ID] [--json OUT]
  .venv/bin/python evals/stability/ablate.py --vote RUN RUN RUN     # simulate voting over repeated runs

Per configuration: score mean +- SE (as pass rate over the chosen questions), questions with the
same outcome in every run, questions with the same answer key in every run. Comparison: delta of
mean pass rate with the SE of the difference, per-question wins (candidate pass rate higher) and
losses, and a verdict: helps when the delta exceeds 2 SE and wins outnumber losses, hurts when
the reverse holds, no effect otherwise. Stability verdict from same-outcome and same-answer
counts. Voting: plurality answer key across runs (outcome = majority outcome of the runs holding
that key), with abstention when no key reaches the agreement threshold.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter
from pathlib import Path

from evals.stability import stability as st

INFORMATIVE = [f"vals-{n:02d}" for n in (3, 23, 36, 38, 40, 1, 2, 6, 8, 25, 33, 42, 46, 48, 49)]


def _load(names: list[str], exclusions: dict) -> list[dict[str, dict]]:
    return [st.load_run(Path(n) if Path(n).is_dir() else st.RUNS / n, exclusions) for n in names]


def config_stats(runs: list[dict[str, dict]], ids: list[str]) -> dict:
    rates = [sum(r[q]["right"] for q in ids) / len(ids) for r in runs]
    mean = statistics.mean(rates)
    se = statistics.stdev(rates) / math.sqrt(len(rates)) if len(rates) > 1 else float("nan")
    per_q = {q: sum(r[q]["right"] for r in runs) / len(runs) for q in ids}
    same_outcome = sum(len({r[q]["right"] for r in runs}) == 1 for q in ids)
    keys = {q: [r[q]["key"] for r in runs] for q in ids}
    comparable = [q for q in ids if all(k is not None for k in keys[q])]
    same_answer = sum(len(set(keys[q])) == 1 for q in comparable)
    return {"n_runs": len(runs), "n_questions": len(ids), "rates": rates, "mean": mean, "se": se,
            "same_outcome": same_outcome, "same_answer": same_answer, "comparable": len(comparable),
            "per_question": per_q}


def compare(base: dict, cand: dict, min_wins: int = 1) -> dict:
    delta = cand["mean"] - base["mean"]
    se = math.sqrt(sum(0 if math.isnan(s["se"]) else s["se"] ** 2 for s in (base, cand)))
    wins = sorted(q for q in base["per_question"] if cand["per_question"][q] > base["per_question"][q])
    losses = sorted(q for q in base["per_question"] if cand["per_question"][q] < base["per_question"][q])
    if min(base["n_runs"], cand["n_runs"]) < 2:
        verdict = "insufficient runs (need N>=2 per side)"
    elif delta > 2 * se and len(wins) - len(losses) >= min_wins:
        verdict = "helps"
    elif delta < -2 * se and len(losses) - len(wins) >= min_wins:
        verdict = "hurts"
    else:
        verdict = "no effect"
    d_outcome = cand["same_outcome"] - base["same_outcome"]
    d_answer = cand["same_answer"] - base["same_answer"]
    stab = "n/a (N<2)" if min(base["n_runs"], cand["n_runs"]) < 2 else "more stable" if d_outcome >= 0 and d_answer > 0 else "less stable" if d_outcome < 0 and d_answer < 0 else "unclear"
    return {"delta": delta, "se": se, "wins": wins, "losses": losses, "verdict": verdict,
            "d_same_outcome": d_outcome, "d_same_answer": d_answer, "stability": stab}


def vote(runs: list[dict[str, dict]], ids: list[str], threshold: int = 2) -> dict:
    """Plurality vote on the answer key. Answers without a key count as their own singleton."""
    right = abstain = wrong_answered = 0
    per_q = {}
    for q in ids:
        keys = [r[q]["key"] if r[q]["key"] is not None else ("nokey", i) for i, r in enumerate(runs)]
        key, n = Counter(keys).most_common(1)[0]
        holders = [r[q]["right"] for r, k in zip(runs, keys) if k == key]
        ok = sum(holders) * 2 > len(holders) if n > 1 else runs[0][q]["right"]
        if n < threshold:
            abstain += 1
            per_q[q] = "abstain"
            continue
        per_q[q] = "right" if ok else "wrong"
        right += ok
        wrong_answered += not ok
    answered = len(ids) - abstain
    return {"vote_right": right, "abstain": abstain, "answered": answered,
            "precision": right / answered if answered else float("nan"),
            "outcome_majority": sum(sum(r[q]["right"] for r in runs) * 2 > len(runs) for q in ids),
            "pass_at_n": sum(any(r[q]["right"] for r in runs) for q in ids),
            "single_mean": statistics.mean(sum(r[q]["right"] for q in ids) for r in runs),
            "per_question": per_q}


def _ids(runs_sets: list[list[dict]], subset: str | None) -> list[str]:
    ids = sorted(set.intersection(*(set(r) for runs in runs_sets for r in runs)))
    if subset == "informative":
        return [q for q in ids if q in INFORMATIVE]
    if subset:
        want = set(subset.split(","))
        return [q for q in ids if q in want]
    return ids


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", nargs="+")
    ap.add_argument("--cand", nargs="+")
    ap.add_argument("--vote", nargs="+")
    ap.add_argument("--threshold", type=int, default=2)
    ap.add_argument("--subset")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    ex = st._load_common().load_exclusions()
    out = {}
    if args.vote:
        runs = _load(args.vote, ex)
        ids = _ids([runs], args.subset)
        v = vote(runs, ids, args.threshold)
        out["vote"] = v
        print(f"{len(ids)} q, {len(runs)} runs: single mean {v['single_mean']:.2f}; vote right {v['vote_right']} "
              f"(abstain {v['abstain']}, precision {v['precision']:.3f}); outcome-majority {v['outcome_majority']}; pass@{len(runs)} {v['pass_at_n']}")
    if args.base and args.cand:
        b, c = _load(args.base, ex), _load(args.cand, ex)
        ids = _ids([b, c], args.subset)
        bs, cs = config_stats(b, ids), config_stats(c, ids)
        cmp_ = compare(bs, cs)
        out.update(base=bs, cand=cs, compare=cmp_)
        for name, s in (("base", bs), ("cand", cs)):
            print(f"{name}: {s['mean']*len(ids):.2f}/{len(ids)} (rate {s['mean']:.3f} +- {s['se']:.3f}, N={s['n_runs']}); "
                  f"same outcome {s['same_outcome']}; same answer {s['same_answer']}/{s['comparable']}")
        print(f"delta {cmp_['delta']*len(ids):+.2f} q ({cmp_['delta']:+.3f} +- {cmp_['se']:.3f}) -> {cmp_['verdict']}; "
              f"wins {' '.join(cmp_['wins']) or '-'}; losses {' '.join(cmp_['losses']) or '-'}; "
              f"stability {cmp_['d_same_outcome']:+d} outcome, {cmp_['d_same_answer']:+d} answer -> {cmp_['stability']}")
    if args.json:
        args.json.write_text(json.dumps(out, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
