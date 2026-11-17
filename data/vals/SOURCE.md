# Vals AI Finance Agent public set

`public.csv` is the public validation set of the Vals AI Finance Agent benchmark, copied unchanged.

| Field | Value |
|---|---|
| Source | https://github.com/vals-ai/finance-agent |
| File | `data/public.csv` |
| Commit | `8ba65f81ab759a8e0d44e72aabc5a47cf839d563` |
| SHA-256 | `901e8cff562819007d43ff0c10b43b2e386481eb40f2157ba18da8fbbe05bff5` |
| License | MIT, Copyright (c) 2025 Vals AI, Inc. See `LICENSE` in this folder. |

Columns: `Question`, `Answer`, `Question Type`, `Expert time (mins)`, `Rubric`.

Each rubric is a JSON list of criteria. The `correctness` criteria must hold in a correct answer; the `contradiction` criterion must not be contradicted. The 50 questions have 200 correctness and 50 contradiction criteria in total.

The file has been public on GitHub since May 2025, so it may be in the training data of current models. The contamination check in `evals/contamination/` tests for that.
