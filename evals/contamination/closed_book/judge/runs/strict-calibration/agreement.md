# Judge agreement — strict-calibration

Model `claude-opus-5-5`, 3 independent passes over 15 closed-book answers, temperature left at the API default.
Prompt template: `evals/contamination/closed_book/judge/judge_prompt_strict.md`. Grading guide: `evals/contamination/closed_book/grading_guide_strict.md`. The judge saw the grading guide, question, official answer, rubric, model answer, and any worked examples in the prompt. It did not see the human reference grades. Those grades were not changed.
Tokens: 352317 in, 44242 out. Cost about $2.2941 at $4.00/$20.00 per million input/output tokens (Opus 5.5 list price). Parse retries: 0. Failures: 0.

n=15 makes kappa noisy; treat the percentages as the main figures.

## Agreement with the human grader

| Compare | Overall agreement | Overall kappa (3-class) | Check agreement | Check kappa (binary) |
|---|---:|---:|---:|---:|
| Run 1 vs human | 100.0% (15/15) | 1.000 | 98.6% (72/73) | 0.971 |
| Run 2 vs human | 100.0% (15/15) | 1.000 | 98.6% (72/73) | 0.971 |
| Run 3 vs human | 93.3% (14/15) | 0.874 | 97.3% (71/73) | 0.943 |
| Majority vote vs human | 100.0% (15/15) | 1.000 | 98.6% (72/73) | 0.971 |

Check-level kappa treats `met`/`triggered` as positive and `not met`/`not triggered` as negative.

## Self-consistency across 3 runs

- Overall labels identical in all 3 runs: 93.3% (14/15)
- Checks identical in all 3 runs: 98.6% (72/73)
- Majority ties: none.

## Overall labels

| Question | human | Run 1 | Run 2 | Run 3 | Majority |
|---|---|---|---|---|---|
| vals-01 | wrong | wrong | wrong | wrong | wrong |
| vals-03 | wrong | wrong | wrong | wrong | wrong |
| vals-04 | wrong | wrong | wrong | wrong | wrong |
| vals-08 | abstain | abstain | abstain | abstain | abstain |
| vals-17 | wrong | wrong | wrong | wrong | wrong |
| vals-22 | wrong | wrong | wrong | wrong | wrong |
| vals-27 | abstain | abstain | abstain | wrong | abstain |
| vals-30 | abstain | abstain | abstain | abstain | abstain |
| vals-33 | wrong | wrong | wrong | wrong | wrong |
| vals-34 | abstain | abstain | abstain | abstain | abstain |
| vals-06 | right | right | right | right | right |
| vals-09 | wrong | wrong | wrong | wrong | wrong |
| vals-12 | wrong | wrong | wrong | wrong | wrong |
| vals-14 | wrong | wrong | wrong | wrong | wrong |
| vals-18 | right | right | right | right | right |

## Disagreements with the human grader

A row appears when any of the three runs, or the majority vote, differs from the human grader. Check-level reasons are the judge's per-check note when present, otherwise the one-line overall reason.

| Question | Check | human | Judge grade(s) | Judge reason | Rule |
|---|---|---|---|---|---|
| vals-01 | 3 (correctness) | met | r1=not met, r2=not met, r3=not met; maj=not met | r1: Says only that the deal would benefit the company; no 'critical to long-term survival' framing. \| r2: The answer says the deal would 'benefit' the company, which is not framing it as critical to long-term survival. \| r3: The answer says only that the deal 'would benefit the company'; no framing as critical to long-term survival. | Correctness: stated fact must match the official meaning. |
| vals-27 | overall | abstain | r1=abstain, r2=abstain, r3=wrong; maj=abstain | Mostly declined to give terms, but committed to a 2067 maturity (meets the final maturity check); amount, coupon, scheduled maturity and redemption terms are missing, and a 2053 issue is an extra unsupported claim. | Abstain rule: refusal vs a committed answer. |
| vals-27 | 3 (correctness) | not met | r1=not met, r2=not met, r3=met; maj=not met | r3: States a 2067 maturity for the older issue. This is a coarser date that identifies the official final maturity. | Loose match for numbers, units, or dates, including the nearby-value guard. |
