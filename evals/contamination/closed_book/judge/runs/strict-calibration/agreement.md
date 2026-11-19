# Judge agreement — strict-calibration

Model `deepseek-v4-pro`, 3 independent passes over 15 closed-book answers, thinking on (temperature does not apply), seed 42 plus the pass number.
Prompt template: `evals/contamination/closed_book/judge/judge_prompt_strict.md`. Grading guide: `evals/contamination/closed_book/grading_guide_strict.md`. The judge saw the grading guide, question, official answer, rubric, model answer, and any worked examples in the prompt. It did not see the human reference grades. Those grades were not changed.
Tokens: 258369 in, 133453 out. Cost about $0.2930 at $0.660/$1.98 per million input/output tokens, cached input $0.022/M (deepseek-v4-pro off-peak list price; peak is 2x). Parse retries: 0. Failures: 0.

n=15 makes kappa noisy; treat the percentages as the main figures.

## Agreement with the human grader

| Compare | Overall agreement | Overall kappa (3-class) | Check agreement | Check kappa (binary) |
|---|---:|---:|---:|---:|
| Run 1 vs human | 86.7% (13/15) | 0.727 | 93.2% (68/73) | 0.858 |
| Run 2 vs human | 93.3% (14/15) | 0.872 | 93.2% (68/73) | 0.858 |
| Run 3 vs human | 86.7% (13/15) | 0.727 | 91.8% (67/73) | 0.828 |
| Majority vote vs human | 86.7% (13/15) | 0.727 | 93.2% (68/73) | 0.858 |

Check-level kappa treats `met`/`triggered` as positive and `not met`/`not triggered` as negative.

## Self-consistency across 3 runs

- Overall labels identical in all 3 runs: 93.3% (14/15)
- Checks identical in all 3 runs: 95.9% (70/73)
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
| vals-27 | abstain | abstain | abstain | abstain | abstain |
| vals-30 | abstain | abstain | abstain | abstain | abstain |
| vals-33 | wrong | wrong | wrong | wrong | wrong |
| vals-34 | abstain | abstain | abstain | abstain | abstain |
| vals-06 | right | wrong | right | wrong | wrong |
| vals-09 | wrong | wrong | wrong | wrong | wrong |
| vals-12 | wrong | wrong | wrong | wrong | wrong |
| vals-14 | wrong | wrong | wrong | wrong | wrong |
| vals-18 | right | wrong | wrong | wrong | wrong |

## Disagreements with the human grader

A row appears when any of the three runs, or the majority vote, differs from the human grader. Check-level reasons are the judge's per-check note when present, otherwise the one-line overall reason.

| Question | Check | human | Judge grade(s) | Judge reason | Rule |
|---|---|---|---|---|---|
| vals-01 | 3 (correctness) | met | r1=not met, r2=not met, r3=not met; maj=not met | r1: Says the deal would benefit the company, not that it was critical to long-term survival. \| r2: Model says the deal would benefit the company but does not state strategic partnership or long-term survival. \| r3: Only says it would benefit the company; lacks the critical long-term survival framing. | Correctness: stated fact must match the official meaning. |
| vals-01 | 9 (contradiction) | not triggered | r1=not triggered, r2=triggered, r3=not triggered; maj=not triggered | r2: States Biden blocked the transaction, conflicting with the official answer's description of Nippon commitments reshaping U.S. Steel operations. | Contradiction triggers only on a conflicting claim, not on omission. |
| vals-06 | overall | right | r1=wrong, r2=right, r3=wrong; maj=wrong | All asked figures are present and the top-spender conclusion is correct, but later revised figures for GOOG and META conflict with the official guidance, triggering contradiction. \| All requested facts are present, but later revised GOOG/META capex figures conflict with the official FY2025 guidance, triggering contradiction. | Overall right requires every correctness check met and no contradiction. |
| vals-06 | 5 (contradiction) | not triggered | r1=triggered, r2=not triggered, r3=triggered; maj=triggered | r1: Model adds later revisions for GOOG and META that conflict with official guidance figures. \| r3: Later revised GOOG (~$85B+) and META ($64-72B) figures conflict with the official FY2025 guidance. | Contradiction triggers only on a conflicting claim, not on omission. |
| vals-12 | 2 (correctness) | not met | r1=met, r2=met, r3=met; maj=met | r1: NT$820.0B–846.2B range contains official 835,152M (NT$835.152B). \| r2: Model gives NT$820.0B–846.2B, which contains the official 835,152 million figure. \| r3: Official NT$835,152M falls inside model's NT$820.0B-846.2B range. | Loose match for numbers, units, or dates, including the nearby-value guard. |
| vals-18 | overall | right | r1=wrong, r2=wrong, r3=wrong; maj=wrong | Identifies gross retention and most definitional elements, but misstates product churn by saying customer churn rather than downgrades, contradicting the official definition. \| Most definitional elements are met, but the answer explicitly describes the metric as focusing on customer churn rather than downgrades, conflicting with the official inclusion of product churn. \| Identifies gross retention and excludes expansion but misstates the calculation and omits/contradicts product churn. | Overall right requires every correctness check met and no contradiction. |
| vals-18 | 3 (correctness) | met | r1=met, r2=met, r3=not met; maj=met | r3: Uses subscription revenue/ACV at beginning minus churn, not ARR from prior period-end compared with current period-end. | Correctness: stated fact must match the official meaning. |
| vals-18 | 4 (correctness) | met | r1=not met, r2=not met, r3=not met; maj=not met | r1: Model describes customer terminations/non-renewals and says customer churn rather than downgrades, omitting product churn. \| r2: States focus on customer churn rather than downgrades, omitting product churn. \| r3: Mentions customer churn only and says customer churn rather than downgrades, omitting product churn. | Names and qualitative claims: meaning must be preserved. |
| vals-18 | 6 (contradiction) | not triggered | r1=triggered, r2=triggered, r3=triggered; maj=triggered | r1: Model states Workday focuses on customer churn rather than downgrades, conflicting with the official inclusion of product or customer churn. \| r2: States the metric focuses on customer churn rather than downgrades, conflicting with official product or customer churn. \| r3: States Workday focuses on customer churn rather than downgrades, conflicting with official product or customer churn. | Contradiction triggers only on a conflicting claim, not on omission. |
