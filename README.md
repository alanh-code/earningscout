# Earningscout

An earnings research agent and the evaluation loop that measures it: questions on SEC filings, gold answers, grading by hand and by an LLM judge, and a record of where the agent fails.

## Layout

| Path | Contents |
|---|---|
| `data/vals/` | The 50 question public set of the Vals AI Finance Agent benchmark, pinned to a source commit |
| `evals/contamination/` | Benchmark contamination check: has the model seen the benchmark data in training? |
| `evals/baseline/` | Native-tools baseline: Sonnet 5.5 answers the 50 public questions with Anthropic built-in tools |
| `evals/verifier/` | Deterministic number verifier used with the LLM judge |

## Benchmark contamination check

This check asks whether the model has seen the benchmark data in training, before any score on it is trusted. The model tested is Claude Sonnet 5.5, and the benchmark is the Vals public set. It also measures how much the model answers from memory alone. Every model call runs in a closed environment: the Anthropic API directly, with no tools, no system prompt and no files.

1. **Pick 10 questions** with a fixed seed: `python3 evals/contamination/select_questions.py`
2. **Completion test** (`evals/contamination/completion/`): the model sees the first part of each of the 50 questions, plus 50 newly written control questions, and is asked for the rest.
3. **Closed book answers** (`evals/contamination/closed_book/`): the model answers the current 10 selected questions from memory; a strict Opus 5.5 judge grades them. A frozen 15-question set from a previous selection keeps the human grades used to calibrate the judge.

See `evals/contamination/README.md` for details.

## Native-tools baseline

Sonnet 5.5 answers the 50 public Vals questions with Anthropic built-in web search, web fetch, and code execution. Gold-host domains (GitHub, Hugging Face, vals.ai, and known mirrors) are blocked on search and fetch for the official run. Answers are graded by a three-pass Claude Opus 5.5 judge using the strict grading guide (`evals/contamination/closed_book/grading_guide_strict.md`), then by a deterministic number verifier: the verifier wins on decided numeric correctness checks, and the judge wins on contradictions. Two questions whose answers depend on an unstated relative time period are left out of the score; the list is `evals/baseline/excluded_questions.csv`.

The scoring protocol as-of date is Thursday, May 1, 2025. That date is after the newest as-of in the gold set (April 7, 2025) and falls in the month the public set appeared on GitHub. It is injected into the system prompt when a question contains "current"; a date given in the question takes precedence.

```bash
.venv/bin/python evals/baseline/native_tools/run.py --name my-run --no-pilot --workers 8 --spend-cap 30
.venv/bin/python evals/verifier/run_verifier.py baseline evals/baseline/native_tools/runs/<name>
.venv/bin/python evals/verifier/apply_policy.py evals/baseline/native_tools/runs/<name>
.venv/bin/python evals/baseline/native_tools/scan_leaks.py evals/baseline/native_tools/runs/<name>
```

The official scored run is `evals/baseline/native_tools/runs/official`: 26 right, 22 wrong, 0 abstain on 48 questions, 54.2% (bootstrap 95% CI 39.6–68.8%). `runs/first-run` is the same protocol without the gold-host domain block: 27 right, 21 wrong, 0 abstain, 56.2% (bootstrap 95% CI 41.7–70.8%). Versus first-run, official flips vals-35 and vals-36 wrong→right and vals-03, vals-10, and vals-40 right→wrong.

## Setup

Requires Python 3.10 or later.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Add an Anthropic API key to `.env` before running any model call.

## License

MIT for this project. The Vals data in `data/vals/` keeps its own MIT license from Vals AI, Inc.
