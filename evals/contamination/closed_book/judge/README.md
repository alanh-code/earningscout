# Closed-book judge

Claude Opus 5.5 grades closed-book answers. The judge sees the grading guide, question, official answer, rubric, and model answer. It never sees human grades.

Default usage grades the frozen human-graded 15 and writes `agreement.md` against those grades. Pass `--answers-dir` to grade a different answer folder (no human comparison):

```bash
.venv/bin/python evals/contamination/closed_book/judge/run_judge.py --dry-run
.venv/bin/python evals/contamination/closed_book/judge/run_judge.py --name my-run
.venv/bin/python evals/contamination/closed_book/judge/run_judge.py --name noleak-calibration --prompt evals/contamination/closed_book/judge/judge_prompt_noleak.md
.venv/bin/python evals/contamination/closed_book/judge/run_judge.py --name selected --answers-dir evals/contamination/closed_book/runs/selected --prompt evals/contamination/closed_book/judge/judge_prompt_strict.md --guide evals/contamination/closed_book/grading_guide_strict.md
```

`judge_prompt.md` includes worked examples from the 15 graded answers, which inflates agreement on those items. `judge_prompt_noleak.md` uses the same closed-book principle with generic examples; use that variant for an honest agreement number. `judge_prompt_strict.md` with `grading_guide_strict.md` is the guide used for the baseline and for `runs/selected`.

The runner resolves `claude-opus-5-5` from the API model list, runs 3 independent passes at the API default temperature, validates the JSON (one retry on a parse failure), and writes `runs/<name>/` (pass `--name`): raw responses, copies of the prompt and guide, `run_meta.json` (model, prompt path, tokens, cost), `judge_grades_run{1,2,3}.csv`, a majority-vote CSV, `summary.md`, and `agreement.md` when human grades are being compared.

Calibration runs against the human-graded 15: `runs/strict-calibration` and `runs/noleak-calibration`. The current selected 10: `runs/selected`.
