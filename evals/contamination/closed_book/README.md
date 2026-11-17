# Closed book answers

The model answers questions from memory alone, in the closed environment. The result is a floor: how much of the task needs no tools at all. Read it together with the completion test, since a correct answer on a question flagged there may come from memorization.

Two answer sets are in this folder:

* `runs/selected`: the current 10 questions in `evals/contamination/questions.csv` (seed 42). Graded by the strict 3-pass Opus 5.5 judge in `judge/runs/selected`. No human grades. Summary: `runs/selected/results.md`.
* `runs/batch-1` and `runs/batch-2`: a frozen 15-question set from a previous selection (the earlier 10 plus `batch2_questions.csv`). Graded by hand first, then by the judge for calibration. Hand grades for all 15 are in `runs/batch-1/grades_human.csv`; `runs/batch-1/results.md` summarizes them.

```bash
.venv/bin/python evals/contamination/closed_book/run_closed_book.py --name selected
.venv/bin/python evals/contamination/closed_book/run_closed_book.py --name batch-1
.venv/bin/python evals/contamination/closed_book/run_closed_book.py --name batch-2 --questions evals/contamination/closed_book/batch2_questions.csv
```
