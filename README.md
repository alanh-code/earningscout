# Earningscout

An earnings research agent and the evaluation loop that measures it: questions on SEC filings, gold answers, grading by hand and by an LLM judge, and a record of where the agent fails.

Earlier work is archived under the git tag `legacy-claude-baseline`.

## Setup

| Part | Choice |
|---|---|
| Benchmark | Vals AI Finance Agent v1.1 public set, 50 questions with reference answers (`data/vals/`) |
| Agent | `deepseek-flash` (DeepSeek V4.1 Flash), thinking on, in a hand-built tool loop (`agent/`) |
| Judge | `deepseek-v4-pro` (DeepSeek V4 Pro), strict grading guide, 3 passes, majority vote |
| Search and fetch | Exa (`/search` type `lite`, `/contents`), published-date cutoff at the protocol as-of date |
| Code execution | E2B sandbox with internet access off, killed after each question |
| Number verifier | Deterministic: an LLM locates the figures, Python compares them (`evals/verifier/`) |
| Seed | 42 |

Model names, prices and peak hours live in `agent/llm.py`; the scoring protocol (as-of date, prompts, blocklist) in `agent/protocol.py`.

## Protocol

* **As-of date:** Thursday, May 1, 2025, after the newest as-of in the gold set (April 7, 2025). It is added to the system prompt when a question says "current"; a date in the question takes precedence.
* **Blocklist:** search results and fetches never reach the gold answers. Blocked: the benchmark repo and dataset hosts (GitHub, Hugging Face, vals.ai, Zenodo and their mirrors), sites that redistribute the dataset or tasks, GitHub CDN and proxy mirrors, the DOI prefixes that resolve to the dataset copies, and agent skills tuned to the benchmark. A URL that wraps a blocked URL (archives, proxies) or names the gold repo is refused too. The list is `BLOCKED_DOMAINS` in `agent/protocol.py`; every run gets a leak scan of its saved tool traces.
* **Budgets per question:** 15 searches, 15 fetches, 30 code runs, 40 turns; the last turn must answer.
* **Scoring:** a question is right when every correctness check in its rubric passes and no contradiction is triggered. The verifier wins on decided numeric correctness checks; the judge wins on contradictions and non-numeric checks. Two questions whose answers depend on an unstated relative time period are not scored (`evals/baseline/excluded_questions.csv`), so 48 are scored.

## Results

**Contamination check** (`evals/contamination/`): no sign that the model memorized the public set. Closed book (no tools) on 10 seeded questions: 0 right, 9 wrong, 1 abstain. Completion test: Vals question endings score no higher than 50 newly written control questions (mean similarity 0.49 vs 0.48 guided, 0.44 vs 0.47 general).

**Judge vs human** on the 15 hand-graded answers (`evals/contamination/closed_book/judge/runs/strict-calibration`): overall 13/15 (Cohen's kappa 0.727), rubric checks 68/73 (kappa 0.858). Both overall disagreements are the judge calling a contradiction the human did not, so the judge errs strict.

**Baseline** (`evals/baseline/agent_loop/runs/`), 3 runs on the 48 scored questions:

| Run | Right | Accuracy | Cost |
|---|---:|---:|---:|
| `official` | 32/48 | 66.7% | $2.00 |
| `repeat_2` | 31/48 | 64.6% | $2.20 |
| `repeat_3` | 30/48 | 62.5% | $2.02 |
| Mean | | **64.6%** (SD 2.1 pts) | about $2 per run |

Verifier and judge agree on 94.9% of decided numeric checks (464/489). The leak scan found no gold-source hits in any run. About half of the cost is Exa and over a third is the judge.

By question type (3 runs pooled):

| Type | Right | Accuracy |
|---|---:|---:|
| Numerical Reasoning | 21/24 | 88% |
| Simple retrieval, Qualitative | 23/27 | 85% |
| Simple retrieval, Quantitative | 20/24 | 83% |
| Adjustments | 7/12 | 58% |
| Beat or Miss | 10/18 | 56% |
| Financial Modeling, Projections | 6/12 | 50% |
| Complex Retrieval | 3/9 | 33% |
| Trends | 3/9 | 33% |
| Market Analysis | 0/9 | 0% |

**Failure taxonomy** (`evals/baseline/agent_loop/failure_taxonomy.md`), primary cause of the 51 wrong answers across the 3 runs:

| Cause | Count |
|---|---:|
| Gold answer is the problem (rounding, narrower than the question) | 11 |
| Different but stated interpretation (basis, peer set, scope) | 10 |
| Data newer than the question implies | 10 |
| Different guidance reference in beat/miss | 7 |
| Retrieved but left out of the answer | 5 |
| Never retrieved (stopped at snippets or the start of a filing) | 4 |
| Misread source | 4 |

15 questions are wrong in all 3 runs.

## Layout

| Path | Contents |
|---|---|
| `agent/` | Model client, scoring protocol, tools (Exa, E2B) and the agent loop, with tests |
| `data/vals/` | The 50-question public set, pinned to a source commit |
| `evals/contamination/` | Contamination check: completion test, closed-book answers, judge and its human calibration |
| `evals/baseline/` | Baseline runner, leak scan, failure taxonomy and the scored runs |
| `evals/verifier/` | Number verifier and the verifier/judge policy step |

## Running it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # add DEEPSEEK_API_KEY, EXA_API_KEY, E2B_API_KEY

.venv/bin/python -m pytest -q agent evals
.venv/bin/python evals/baseline/agent_loop/run.py --name my-run --workers 8 --spend-cap 6
.venv/bin/python evals/verifier/run_verifier.py baseline evals/baseline/agent_loop/runs/my-run
.venv/bin/python evals/verifier/apply_policy.py evals/baseline/agent_loop/runs/my-run
.venv/bin/python evals/baseline/scan_leaks.py evals/baseline/agent_loop/runs/my-run
```

Runs refuse to start, and pause before any paid call, during DeepSeek peak hours unless `--allow-peak` is passed; `--resume --run-dir <run>` continues a paused run. Requires Python 3.10 or later.

## License

MIT for this project. The Vals data in `data/vals/` keeps its own MIT license from Vals AI, Inc.
