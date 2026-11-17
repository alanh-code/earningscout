# Judge agreement — noleak-calibration

Model `claude-opus-5-5`, 3 independent passes over 15 closed-book answers, temperature left at the API default.
Prompt template: `evals/contamination/closed_book/judge/judge_prompt_noleak.md`. The judge saw the grading guide, question, official answer, rubric, model answer, and any worked examples in the prompt. It did not see the human reference grades. Those grades were not changed.
Tokens: 342102 in, 47592 out. Cost about $2.3202 at $4.00/$20.00 per million input/output tokens (Opus 5.5 list price). Parse retries: 0. Failures: 0.

n=15 makes kappa noisy; treat the percentages as the main figures.

## Agreement with the human grader

| Compare | Overall agreement | Overall kappa (3-class) | Check agreement | Check kappa (binary) |
|---|---:|---:|---:|---:|
| Run 1 vs human | 86.7% (13/15) | 0.792 | 84.9% (62/73) | 0.698 |
| Run 2 vs human | 86.7% (13/15) | 0.792 | 84.9% (62/73) | 0.698 |
| Run 3 vs human | 86.7% (13/15) | 0.792 | 84.9% (62/73) | 0.698 |
| Majority vote vs human | 86.7% (13/15) | 0.792 | 84.9% (62/73) | 0.698 |

Check-level kappa treats `met`/`triggered` as positive and `not met`/`not triggered` as negative.

## Self-consistency across 3 runs

- Overall labels identical in all 3 runs: 100.0% (15/15)
- Checks identical in all 3 runs: 100.0% (73/73)
- Majority ties: none.

## Overall labels

| Question | human | Run 1 | Run 2 | Run 3 | Majority |
|---|---|---|---|---|---|
| vals-01 | wrong | wrong | wrong | wrong | wrong |
| vals-03 | wrong | wrong | wrong | wrong | wrong |
| vals-04 | right | right | right | right | right |
| vals-08 | abstain | abstain | abstain | abstain | abstain |
| vals-17 | right | right | right | right | right |
| vals-22 | wrong | wrong | wrong | wrong | wrong |
| vals-27 | abstain | wrong | wrong | wrong | wrong |
| vals-30 | abstain | abstain | abstain | abstain | abstain |
| vals-33 | wrong | right | right | right | right |
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
| vals-01 | 3 (correctness) | met | r1=not met, r2=not met, r3=not met; maj=not met | r1: Says only that the deal 'would benefit the company'; nothing about it being critical to long-term survival. \| r2: Says only that the deal would 'benefit the company'; nothing about it being critical to long-term survival. \| r3: Says only that the deal 'would benefit the company'; no framing as critical to long-term survival. | Correctness: stated fact must match the official meaning. |
| vals-22 | 2 (correctness) | not met | r1=met, r2=met, r3=met; maj=met | r1: $164.70 is about 0.7% off. It is closer to $163.51 than to the other official figures. \| r2: $164.70 is about 0.7% off. It is closer to $163.51 than to the FY2024 figure of $166.23. \| r3: $164.70 is about 0.7% off and closer to $163.51 than to the FY2024 figure of $166.23. | Loose match for numbers, units, or dates, including the nearby-value guard. |
| vals-22 | 3 (correctness) | not met | r1=met, r2=met, r3=met; maj=met | r1: $167.10 is about 0.5% off. It is closer to $166.23 than to the other official figures. \| r2: $167.10 is about 0.5% off, close enough to show the model knows the fact. \| r3: $167.10 is about 0.5% off and closest to the FY2024 figure. | Loose match for numbers, units, or dates, including the nearby-value guard. |
| vals-27 | overall | abstain | r1=wrong, r2=wrong, r3=wrong; maj=wrong | The answer is largely a refusal but commits to a 2067 maturity (met); it omits the $500M Series A 6.5% amount, the 2057 scheduled maturity, and the 2037 call terms, and adds an extra hedged claim about a 2053 issue. \| Mostly declined, but committed to a hedged 2067 maturity that matches the final maturity. Amount, coupon, 2057 scheduled maturity and redemption terms are missing. A hedged 2053/2013-issue claim is noted as extra. \| This is a partial answer, not an abstain: it largely declines but commits to a 2067 maturity, which meets the final maturity check. Amount, coupon, 2057 scheduled maturity, and redemption terms are missing; the 2053 claim is an extra outside the official text. | Abstain rule: refusal vs a committed answer. |
| vals-27 | 3 (correctness) | not met | r1=met, r2=met, r3=met; maj=met | r1: Commits to a 2067 maturity for the older junior subordinated issue, which identifies the official final maturity year. \| r2: The model commits to a hedged 2067 maturity for 'the older issue'. Under loose matching, the year alone identifies the official date. \| r3: It commits to a 2067 maturity for the older issue. A year-only date still identifies the official final maturity. | Loose match for numbers, units, or dates, including the nearby-value guard. |
| vals-33 | overall | wrong | r1=right, r2=right, r3=right; maj=right | The primary scenario gives ~-$1.27B and ~11% loss widening, both close to the official -$1.261B and 10.7% decrease; the extra no-tax scenario (-$1.6B, ~14%) is an alternative estimate under the multiple-candidates rule. \| The primary scenario (~$1.27B hit, loss widens ~11%) closely matches the official $1.261B / 10.7% decrease; the extra no-tax scenario is an alternative estimate, not a contradiction. \| The 21%-tax case (~$1.27B hit, loss widens ~11%) closely matches the official $1.261B and 10.7% decrease; the extra no-tax scenario (~$1.6B, ~14%) is offered as an alternative and does not fail the checks. | Overall right requires every correctness check met and no contradiction. |
| vals-33 | 1 (correctness) | not met | r1=met, r2=met, r3=met; maj=met | r1: The main 21%-tax-shield calculation gives a -$1.27B reduction to net income, within 1% of $1.261B with the correct negative direction. The no-tax-benefit scenario of -$1.6B is an extra estimate, and the guide allows other estimates when a close figure is given. \| r2: The primary 21% tax-shield scenario gives a ~$1.27B reduction, within 1% of $1.261B. The extra no-tax-benefit estimate of $1.6B is an additional scenario, which the guide allows. \| r3: The 21% tax-shield case gives a ~$1.27B reduction in net income, within 1% of $1.261B, and the direction is negative. The alternative $1.6B no-tax scenario is mentioned as another estimate, not as the sole committed figure. | Loose match for numbers, units, or dates, including the nearby-value guard. |
| vals-33 | 2 (correctness) | not met | r1=met, r2=met, r3=met; maj=met | r1: 'Loss widens ~11%' is a decrease in net income of about 11%, within a few percent of 10.7% and in the right direction. \| r2: 'Loss widens ~11%' has the same direction (net income falls) and is close to 10.7%. \| r3: 'Loss widens ~11%' means net income falls by about 11%, which is close to 10.7% and in the same direction. | Loose match for numbers, units, or dates, including the nearby-value guard. |
| vals-12 | 2 (correctness) | not met | r1=met, r2=met, r3=met; maj=met | r1: Model uses 32.8 and gives a midpoint of about NT$833B, within about 0.3% of 835,152. \| r2: Model midpoint ≈ NT$833B at 32.8. This is within ~0.3% of 835,152 and is not closer to another official figure. \| r3: Model gives a midpoint of about NT$833B at 32.8. That is within about 0.3% of 835,152 and closer to it than to any other official figure. | Loose match for numbers, units, or dates, including the nearby-value guard. |
| vals-12 | 7 (correctness) | not met | r1=met, r2=met, r3=met; maj=met | r1: Model states about NT$260.01B. \| r2: Model states ≈ NT$260.01B. \| r3: Model states about NT$260.01B. | Loose match for numbers, units, or dates, including the nearby-value guard. |
| vals-12 | 9 (correctness) | not met | r1=met, r2=met, r3=met; maj=met | r1: Model gives NT$810.2B, about 1.8% off and closer to 825,107 than to any other official figure. \| r2: Model states NT$810.2B, ~1.8% off. This is within a few percent and closer to 825,107 than to guidance, though it was derived from wrong inputs. \| r3: Model states NT$810.2B, about 1.8% below the official figure. That is within a few percent and not closer to another official figure, though it was derived from wrong inputs. | Loose match for numbers, units, or dates, including the nearby-value guard. |
| vals-12 | 10 (correctness) | met | r1=not met, r2=not met, r3=not met; maj=not met | r1: Direction (miss) is right, but the headline miss vs. midpoint is -2.8%, not -1.2%. The model's -1.2% is measured against the low end, a different comparison. \| r2: Model's headline is a miss of ~2.8% vs midpoint. Its -1.2% figure is measured against the low end, a different baseline. \| r3: Model's headline is a miss of about 2.8% versus the guidance midpoint. Its -1.2% is measured against the low end, not the official guidance basis. | Loose match for numbers, units, or dates, including the nearby-value guard. |
| vals-14 | 1 (correctness) | not met | r1=met, r2=met, r3=met; maj=met | r1: Model gives ~13–14%. The lower end is within a few percent of 12.7%, and it is not closer to another official figure. \| r2: Model gives ~13–14%. The low end is close to 12.7%, and no other official figure sits nearby. \| r3: The model gives ~13–14% and calls it low-teens. The lower bound is within a few percent of 12.7%, and no other official figure is closer. | Loose match for numbers, units, or dates, including the nearby-value guard. |

## Judge internal consistency

- vals-22 run 1: rubric_fraction stated 0.6667 vs 0.6667 from checks
- vals-22 run 2: rubric_fraction stated 0.6667 vs 0.6667 from checks
- vals-22 run 3: rubric_fraction stated 0.6667 vs 0.6667 from checks


## Agreement with the human grader after grade revisions (`grades_human.csv`)

Two of the human grades were revised after seeing this judge run: vals-27 overall abstain→wrong (the model committed to a 2067 maturity, so it is not a refusal; check results, including check 3 not met, were left unchanged), and vals-33 overall wrong→right (both correctness checks met; contradiction not triggered). Because those revisions were made after seeing the judge, the agreement below is partly anchored and is more generous than the figures above.

| Compare | Overall agreement | Overall kappa (3-class) | Check agreement | Check kappa (binary) |
|---|---:|---:|---:|---:|
| Run 1 vs human (v2) | 100.0% (15/15) | 1.000 | 87.7% (64/73) | 0.753 |
| Run 2 vs human (v2) | 100.0% (15/15) | 1.000 | 87.7% (64/73) | 0.753 |
| Run 3 vs human (v2) | 100.0% (15/15) | 1.000 | 87.7% (64/73) | 0.753 |
| Majority vote vs human (v2) | 100.0% (15/15) | 1.000 | 87.7% (64/73) | 0.753 |

Overall labels now agree on all 15 questions. Nine check-level disagreements remain (vals-01 check 3; vals-22 checks 2–3; vals-27 check 3; vals-12 checks 2, 7, 9–10; vals-14 check 1).
