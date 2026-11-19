# Benchmark contamination check

**Question:** has the model seen the benchmark data in training? Here the model is the agent model, `deepseek-flash`, and the benchmark is the Vals Finance Agent public set. It also measures how many questions the model answers from memory alone.

The public set has been on GitHub since May 2025. If the model memorized it, any later score on these questions measures recall, not research.

## Closed environment

Every model call in this check:

* goes straight to the DeepSeek API, never through an app or agent that brings its own tools, memory or files
* sends no `tools`, no system prompt and no files, with thinking off, temperature 0 and seed 42
* is one fresh request, never several questions in one conversation
* is checked after the response (`closed_violations` in `agent/llm.py`): one plain text answer, no tool calls, no thinking output, `finish_reason` `stop`, served by the requested model

Without this, web search could simply find the questions on GitHub.

## Steps

| Step | Folder | What it does |
|---|---|---|
| 1 | this folder | `select_questions.py` picks 10 questions into `questions.csv` |
| 2 | `completion/` | Completion test on all 50 questions plus the 50 control questions in `controls.csv` |
| 3 | `closed_book/` | The model answers the current 10 (`runs/selected`) and, separately, a frozen human-graded 15 |
| 4 | `closed_book/judge/` | The `deepseek-v4-pro` judge grades the answers (strict guide for the current 10; calibration vs human on the 15) |

## The 10 questions

`questions.csv` holds one question from each of the 9 Vals question types plus one more Simple retrieval, Quantitative question, picked with seed `42`. Ids are row numbers in `data/vals/public.csv`. Do not swap questions after reading them; rerunning the script gives the same file.

Current ids: vals-01, 03, 11, 16, 17, 18, 19, 31, 33, 44. vals-11 is also listed in `evals/baseline/excluded_questions.csv` (answer depends on an unstated relative time period); it stays in this set.

A previous seed produced vals-01, 03, 04, 08, 17, 22, 27, 30, 33, 34. That set, plus five more in `closed_book/batch2_questions.csv` (vals-06, 09, 12, 14, 18), is the human-graded 15 in `closed_book/runs/batch-1` and `batch-2`. Those answers and their human grades are a frozen calibration set for the judge.

## Scoring

Every question counts equally.

* **Accuracy** (main score): a question scores 1 when every correctness criterion in its rubric passes and the contradiction criterion is not triggered, otherwise 0.
* **Rubric fraction** (second score): criteria passed divided by criteria total, averaged over questions.

Both are also reported by question type.

## Results

**Completion** (`completion/runs/official`): 200 requests, all passed the closed-environment checks. Score is embedding cosine similarity with `all-mpnet-base-v2`.

| Group | Mode | n | Mean | Median | Min | Max |
|---|---|---|---|---|---|---|
| vals | guided | 50 | 0.49 | 0.47 | 0.03 | 0.94 |
| vals | general | 50 | 0.44 | 0.46 | -0.06 | 0.92 |
| control | guided | 50 | 0.48 | 0.50 | 0.06 | 0.83 |
| control | general | 50 | 0.47 | 0.48 | 0.03 | 0.99 |

Vals is not above control on either prompt, and guided is above general on only 49 of 100 questions. The highest-scoring Vals endings change the period or wording (see `completion/runs/official/summary.md`). Cost about $0.004.

**Closed book, current 10** (`closed_book/runs/selected`, graded in `closed_book/judge/runs/selected` by the strict 3-pass judge): 0 right, 9 wrong, 1 abstain (vals-31); average rubric fraction 0.19. Cost about $0.15.

**Judge calibration** (`closed_book/judge/runs/strict-calibration`, the human-graded 15): majority vote matches the human overall label on 13/15 (kappa 0.727) and the rubric checks on 68/73 (kappa 0.858). The two overall disagreements (vals-06, vals-18) are contradictions the judge triggered and the human did not; see `agreement.md`.

**Conclusion:** no sign that the model memorized the public set. Completion similarity for Vals is at the control level, and closed-book accuracy is far below the tool-using baseline.
