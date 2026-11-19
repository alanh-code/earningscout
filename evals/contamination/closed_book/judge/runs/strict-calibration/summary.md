# Judge run strict-calibration

Model `deepseek-v4-pro`, 15 answers, 3 independent passes, thinking on (temperature does not apply), seed 42 plus the pass number.
Prompt template: `evals/contamination/closed_book/judge/judge_prompt_strict.md`. Grading guide: `evals/contamination/closed_book/grading_guide_strict.md`. Judge inputs: grading guide, question, official answer, rubric, model answer, and any worked examples in the prompt. Human reference grades were not sent.
Tokens: 258369 in, 133453 out. Cost about $0.2930 at $0.660/$1.98 per million input/output tokens, cached input $0.022/M (deepseek-v4-pro off-peak list price; peak is 2x).
Parse retries: 0. Failures: 0.
