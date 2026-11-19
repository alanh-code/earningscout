# Closed-book judge

The judge model in `agent/llm.py` (`deepseek-v4-pro`, thinking on) grades closed-book answers. It sees the grading guide, question, official answer, rubric, and model answer. It never sees human grades.

Default usage grades the frozen human-graded 15 and writes `agreement.md` against those grades. Pass `--answers-dir` to grade a different answer folder (no human comparison):

```bash
.venv/bin/python evals/contamination/closed_book/judge/run_judge.py --dry-run
.venv/bin/python evals/contamination/closed_book/judge/run_judge.py --name strict-calibration --prompt evals/contamination/closed_book/judge/judge_prompt_strict.md --guide evals/contamination/closed_book/grading_guide_strict.md
.venv/bin/python evals/contamination/closed_book/judge/run_judge.py --name selected --answers-dir evals/contamination/closed_book/runs/selected --prompt evals/contamination/closed_book/judge/judge_prompt_strict.md --guide evals/contamination/closed_book/grading_guide_strict.md
```

`judge_prompt.md` includes worked examples from the 15 graded answers, which inflates agreement on those items; `judge_prompt_noleak.md` uses generic examples. `judge_prompt_strict.md` with `grading_guide_strict.md` is the setting used for the baseline, the calibration and `runs/selected`.

The runner checks the model id against the provider's model list, runs 3 independent passes (seed 42 plus the pass number), validates the JSON (one retry on a parse failure), and writes `runs/<name>/`: raw responses, copies of the prompt and guide, `run_meta.json` (model, prompt path, tokens, cost), `judge_grades_run{1,2,3}.csv`, a majority-vote CSV, `summary.md`, and `agreement.md` when human grades are compared.

* `runs/strict-calibration`: the human-graded 15; 13/15 overall (kappa 0.727), 68/73 checks (kappa 0.858).
* `runs/selected`: the current 10; 0 right, 9 wrong, 1 abstain.
