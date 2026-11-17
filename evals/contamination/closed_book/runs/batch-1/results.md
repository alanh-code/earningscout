# Closed-book results — 15 questions

Graded by hand under the strict grading guide. Model: claude-sonnet-5-5, no tools or system prompt. Source: `grades_human.csv`.

These are the final human grades: after an earlier post-judge revision, the answers were re-graded under the strict rule, then vals-12 check 10 was marked `not met` and vals-27 overall was marked `abstain`. The shipped strict-calibration agreement table uses these labels (15/15 overall, 72/73 checks). An earlier summary in this file reported 5/15 from a pre-strict-regrade snapshot; that figure was out of date.

Runs: `batch-1` (vals-01, 03, 04, 08, 17, 22, 27, 30, 33, 34); `batch-2` (vals-06, 09, 12, 14, 18).

## Summary

| | n | Right | Wrong | Abstain | Accuracy (right/n) | Accuracy among attempted | Avg rubric fraction | Abstain rate | Triggered contradictions |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| All 15 | 15 | 2 | 9 | 4 | 13.3% (2/15) | 18.2% (2/11) | 0.285 | 26.7% (4/15) | 8 |
| Batch 1 | 10 | 0 | 6 | 4 | 0.0% (0/10) | 0.0% (0/6) | 0.188 | 40.0% (4/10) | 5 |
| Batch 2 | 5 | 2 | 3 | 0 | 40.0% (2/5) | 40.0% (2/5) | 0.480 | 0.0% (0/5) | 3 |

Accuracy among attempted is right/(n − abstain). Rubric fraction is correctness met / correctness total, averaged over questions (abstains included at 0).

## Detail

- Right: vals-06, vals-18
- Wrong: vals-01, vals-03, vals-04, vals-09, vals-12, vals-14, vals-17, vals-22, vals-33
- Abstain (refused / no answer to the asked figure): vals-08, vals-27, vals-30, vals-34
- Triggered contradictions (confident wrong figures): vals-03, vals-04, vals-09, vals-12, vals-14, vals-17, vals-22, vals-33
