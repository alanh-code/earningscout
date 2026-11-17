# Closed-book results — current selected 10

Fresh answers in this folder, graded by the strict 3-pass Claude Opus 5.5 judge in `evals/contamination/closed_book/judge/runs/selected`. There are no human grades for this run. Source: `judge_grades_majority.csv`.

The human-graded 15 (previous selection in `batch-1`, plus `batch-2`) is a separate, frozen calibration record. See `runs/batch-1/results.md`.

The 10 questions, picked with seed 42: vals-01, 03, 11, 16, 17, 18, 19, 31, 33, 44. vals-11 is also a baseline exclusion (answer depends on an unstated relative time period); it stays in this set.

## Summary

| | n | Right | Wrong | Abstain | Accuracy (right/n) | Accuracy among attempted | Avg rubric fraction | Abstain rate | Triggered contradictions |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Selected 10 | 10 | 1 | 6 | 3 | 10.0% (1/10) | 14.3% (1/7) | 0.1625 | 30.0% (3/10) | 5 |

Accuracy among attempted is right/(n − abstain). Rubric fraction is correctness met / correctness total, averaged over questions (abstains included at 0).

A number verifier compared with the judge majority on this run (`evals/verifier/runs/selected`): 18/19 decided numeric checks agree. The one disagreement is vals-33 check 1 (verifier `met`, judge `not met`). The overall label stays `wrong` because the contradiction check is triggered, which the judge still decides.

## Detail

- Right: vals-18
- Wrong: vals-01, vals-03, vals-11, vals-17, vals-31, vals-33
- Abstain: vals-16, vals-19, vals-44
- Triggered contradictions: vals-03, vals-11, vals-17, vals-31, vals-33

Four ids overlap the previous 10 (vals-01, 03, 17, 33). This run is a new sample of answers, not a regrade of `batch-1`. On the overlap, the human grades on the earlier answers were wrong, wrong, right, right; the judge on these new answers is wrong, wrong, wrong, wrong.
