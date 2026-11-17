# Benchmark contamination check

**Question:** has the model seen the benchmark data in training? Here the model is Claude Sonnet 5.5 and the benchmark is the Vals Finance Agent public set. It also measures how many questions the model answers from memory alone.

The public set has been on GitHub since May 2025, before the model's training cutoff. If the model memorized it, any later score on these questions measures recall, not research.

## Closed environment

Every model call in this check:

* goes straight to the Anthropic Messages API, never through an app or agent that brings its own tools, memory or files
* sends no `tools`, no system prompt and no files
* is one fresh request, never several questions in one conversation
* is checked after the response: every content block is `text`, `stop_reason` is not `tool_use`, and `usage` shows no server tool use

Without this, web search could simply find the questions on GitHub.

## Steps

| Step | Folder | What it does |
|---|---|---|
| 1 | this folder | `select_questions.py` picks 10 questions into `questions.csv` |
| 2 | `completion/` | Completion test on all 50 questions plus the 50 control questions in `controls.csv` |
| 3 | `closed_book/` | The model answers the current 10 (`runs/selected`) and, separately, a frozen human-graded 15 |
| 4 | `closed_book/judge/` | A Claude Opus 5.5 judge grades the answers (strict guide for the current 10; calibration vs human on the 15) |

## The 10 questions

`questions.csv` holds one question from each of the 9 Vals question types plus one more Simple retrieval, Quantitative question, picked with seed `42`. Ids are row numbers in `data/vals/public.csv`. Do not swap questions after reading them; rerunning the script gives the same file.

Current ids: vals-01, 03, 11, 16, 17, 18, 19, 31, 33, 44. vals-11 is also listed in `evals/baseline/excluded_questions.csv` (answer depends on an unstated relative time period); it stays in this set.

A previous seed produced vals-01, 03, 04, 08, 17, 22, 27, 30, 33, 34. That set, plus five more in `closed_book/batch2_questions.csv` (vals-06, 09, 12, 14, 18), is the human-graded 15 in `closed_book/runs/batch-1` and `batch-2`. Those answers, human grades, and judge calibrations are kept as a frozen record. They were not re-collected for the current 10.

## Scoring

Every question counts equally.

* **Accuracy** (main score): a question scores 1 when every correctness criterion in its rubric passes and the contradiction criterion is not triggered, otherwise 0.
* **Rubric fraction** (second score): criteria passed divided by criteria total, averaged over questions.

Both are also reported by question type.

## Results

**Completion** (`completion/runs/official`): 200 requests, all passed the closed-environment checks. Score is embedding cosine similarity with `all-mpnet-base-v2`.

| Group | Mode | n | Mean | Median | Min | Max |
|---|---|---|---|---|---|---|
| vals | guided | 50 | 0.51 | 0.50 | 0.23 | 0.81 |
| vals | general | 50 | 0.44 | 0.42 | 0.09 | 0.82 |
| control | guided | 50 | 0.53 | 0.55 | 0.14 | 0.87 |
| control | general | 50 | 0.54 | 0.56 | 0.13 | 0.86 |

Vals is not above control on either prompt. Guided is above general on 60 of 100 questions. Cost about $0.13. See `completion/runs/official/summary.md` and `analysis.md`. The `selected` flags in `results.csv` mark the current 10; they do not change the Vals-versus-control stats.

**Closed book, human-graded 15** (previous 10 plus five more): 2 right, 9 wrong, 4 abstain, 13.3% (2/15). See `closed_book/runs/batch-1/results.md`.

**Closed book, current 10** (`closed_book/runs/selected`): fresh answers, graded by the same strict 3-pass Opus 5.5 judge used for the baseline. No new human grades. 1 right, 6 wrong, 3 abstain, 10.0% (1/10); 14.3% (1/7) among attempted. Average rubric fraction 0.1625. See `closed_book/runs/selected/results.md`.

**Conclusion:** No sign that Sonnet 5.5 memorized the public set. Completion similarity for Vals is at or below the control questions, and closed-book accuracy is well below the tool-using baseline. Changing the selection seed did not change that conclusion.
