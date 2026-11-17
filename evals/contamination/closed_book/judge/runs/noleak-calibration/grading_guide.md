# Closed-book grading guide

For human and LLM judges scoring Claude Sonnet 5.5 closed-book answers to the 50 public Vals Finance Agent questions (no tools). Checks come from the `Rubric` column in `data/vals/public.csv`. This is not an official Vals grading key.

## Procedure

1. Score each `correctness` check as `met` or `not met`.
2. Score the `contradiction` check as `triggered` or `not triggered`.
3. Compute rubric fraction from correctness checks only.
4. Assign overall `right`, `wrong`, or `abstain`.
5. Write a one-line reason.

Paraphrase is fine. Wording, order, and formatting do not matter if the meaning matches. A bundled check (several facts in one `criteria` string) is met if every fact in that string is met, including by a substantively equivalent description. Silence on a fact is `not met`, not a contradiction.

## Closed-book principle

Closed-book grading asks whether the model knows the fact, not whether it recalled the official figure to the last digit. A correctness check is `met` if the answer shows the model knows the fact: close values or ranges (within a few percent), slightly different wording, or a substantively equivalent description all count.

Keep the guard only for clear mismatches: a wrong period, the wrong sign or direction, or a value closer to a different figure the question asks about.

Tool-using answers may need stricter matching.

## Correctness checks

**Names and qualitative claims.** The identity or claim must be the same. Middle initials and punctuation may be dropped if the referent is unambiguous (`David Burritt` meets `David B. Burritt`). Slightly different wording or a substantively equivalent description is `met`. A restated claim that changes the official meaning is not (`virtually flat` meets `Take rate was virtually flat from 2023 to 2024`; `declined slightly` does not meet `declined substantially`). Exact official wording is not required.

**Lists.** Each listed item is usually its own check (directors, EBITDA adjustments, guidance metrics). Extra correct items do not help or hurt.

## Numbers, units, and dates

Convert to the same unit and scale before comparing. Official answers in this set already mix scale: Q15 writes the same inventory as `$2,168M` and `2.168B`.

**Loose match.** After unit conversion, a number or date is `met` if it equals the official value, or is a rounded or coarser form that is still generally right. `18` meets `18.02`. `announced in December 2023` meets `announced on December 18, 2023`. A more precise value that rounds to the official figure also meets it. Under the closed-book principle, a close value or range (within a few percent of the official figure) is also `met`, even when it is not a rounding of the official number.

The check is `not met` only for a clear mismatch: a wrong period, the wrong sign or direction, or a value closer to a different figure the question asks about (for example, stating Netflix ARPU as `11` for official `10.82` when the same question also has `10.91`, which is closer to `11`). A slightly off value in a tight official series is still `met` if it is within a few percent and is not clearly the wrong period or line item.

Do not use a blanket ±1% relative band as a hard cutoff. Adjacent official values can sit closer than 1% (Netflix ARPU `10.82` vs `10.91`, Airbnb take rate `13.3` / `13.5` / `13.6`, Uber take rate `27.04` vs `27.02`). Closeness within a few percent still counts as knowing the fact, unless the stated value is a clear mismatch under the guard above.

Patterns in this rubric set:

- **Official figures may already be rounded.** `45% (102,000/228,000)` is ~44.74%; the 2-year CAGR `22.6%` and the average February–March growth `4.5%` are rounded. A more precise `44.7%` or `22.61%` meets those checks; a coarser `23%` for `22.6%` also meets them if no nearby official figure would also fit.
- **Question-specified rounding.** Q31 asks to “round to nearest million” (`$467 million`). Values that round to 467 million meet it.
- **“Approximately.”** Hedging language does not change the loose-match rule. `approximately 2.8%` is met by `2.81` and by `about 3%`, unless a nearby official figure would also fit. Qualitative wording such as `roughly flat` or `virtually flat` is met by equivalent language (flat, little changed), not by a different numeric trend.
- **Units and scale must be equivalent, not merely the same digits.** `$3,250 million` meets `$3.25 Billion`. `$14,426,266,000` and `$1,407,000,000` are full dollars. When the rubric says `in thousands` (Q19 `$85,002 thousands`, Q32 `$12,057,993 in thousands`), accept that scale or an equivalent restatement (`$12.058 billion`), not the bare digits as dollars. If the rubric gives a bare number (Q10 `2,865,507`), accept the same digits at the official answer’s scale, or a coarser rounding that still identifies that figure (`$2.9B` meets).
- **Currency is a unit.** An `NT$` figure in Q12 does not meet a USD check, and vice versa.
- **Percent, points, and bps.** Equivalent conversions meet the check: `140bps` = `1.4 percentage points`; `410bps` is the change from `6.8%` to `10.9%`, not `410%` and not `4.10%` of the starting rate. Load factor `0.824` = `82.4%`; payout ratio `0.83` = `83%`. A wrong unit that changes the value fails (`beat by 140%` does not meet `140bps BEAT`).
- **Sign and direction are part of the fact.** `-0.8%` is not `0.8%`. `140bps miss` does not meet `140bps BEAT`. `below the high end` does not meet `above high end of range`. `10.7% decrease` is required, not an increase. `$(149.7) Million` is a loss.
- **Dates and years.** A coarser date can meet a more precise official date if it still clearly identifies it (`announced in December 2023` meets `announced on December 18, 2023`). A different day does not (`December 19, 2023` does not meet `December 18, 2023`). Year-only checks (`Production expected to begin in 2025`) do not need a month. Do not treat a company’s fiscal year as a calendar year, or the reverse, unless they coincide. This set includes fiscal periods that are not calendar years (Oracle year ended 5/31/2024, TJX Q4 FY 2025, General Mills FY2023–FY2025). A correct figure assigned to the wrong period or year fails.

## Contradiction

In this file the `contradiction` criterion is almost always the official answer text, not a separate “gotcha” list. It is triggered only if the model *states* something inconsistent with that text. Omissions do not trigger it. A close value, close range, or substantively equivalent description that meets the corresponding correctness check does not trigger contradiction.

If contradiction is triggered, the overall grade is `wrong`, even when every correctness check is `met`. Some official-answer facts appear only in the contradiction text (for example, parts of Q1).

## Hedges, ranges, and multiple candidates

- A correct or close value with hedging language (`approximately $3.25 billion`) is `met` if the number itself meets the numeric rule or the closed-book principle.
- An official range is `met` if the stated range is that range, or is close (within a few percent), including a slightly shifted range of the same width.
- An open-ended bound that targets the official figure can be `met`: `about $100 billion or more` can meet a figure around `$100 billion` (such as `$105.2 billion`). The older rule that treated any open-ended or containing range as `not met` is dropped for closed-book grading.
- A wide range or bound is `not met` only when it is so broad, or so far off, that it no longer shows knowledge of the fact.
- If the model gives the official or close figure and also mentions later revisions or other estimates, the check can still be `met`. A committed candidate is `not met` only if it is a clear mismatch (wrong period, wrong sign or direction, or a value closer to a different figure).
- `About $3 billion` for `$3.25 Billion` is `met`. `11` for Netflix ARPU `10.82` is `not met` when `10.91` is also in the question, because `11` is closer to the other official figure.

## Abstain

`abstain` if the model refuses to give the asked figure, or says it does not know, and does not commit to a candidate value for what was asked. Mentioning other, unrelated figures does not change this. Score all correctness checks `not met`, rubric fraction `0`, contradiction `not triggered`, overall `abstain`.

A guess after “I’m not sure, but…” is not an abstain if it commits to a candidate value for what was asked; grade the guess. A partial answer that attempts some of the asked checks is not an abstain; grade what was stated and treat the rest as `not met`. Overall is then `wrong` unless every correctness check is still met and contradiction is not triggered.

## Wrong reasoning and extra claims

Correctness grades stated facts, not the quality of the working. A correct final figure with a wrong method still meets that figure’s check; note the method error in the reason. If the working itself states a wrong input that is also a correctness check, that input check is `not met`.

Extra correct detail is ignored. Extra wrong claims:

- If they conflict with the official answer / contradiction text, trigger contradiction and overall is `wrong`.
- If they are outside that text, they do not change checks, fraction, or overall; mention them in the reason.

## Outputs per answer

| Field | Value |
|---|---|
| Each correctness check | `met` or `not met` |
| Contradiction check | `triggered` or `not triggered` |
| Rubric fraction | (correctness met) / (correctness total) |
| Overall | `right` if every correctness check is `met`, contradiction is not triggered, and the answer is not an abstain; `abstain` as defined above; otherwise `wrong` |
| Reason | one line |

Do not use a “partly correct” overall label. Partial credit is the rubric fraction. Report accuracy as `right / n`, and report the abstain rate separately.

## Judge prompt

```
You are grading a closed-book answer against a fixed rubric. Follow the grading guide below exactly. Do not reward style, length, or confidence. Do not use any knowledge except the question, official answer, rubric, and guide.

<grading_guide>
{{paste this guide in full}}
</grading_guide>

<question>{{question}}</question>
<official_answer>{{official answer}}</official_answer>
<rubric>{{JSON list of {operator, criteria}}}</rubric>
<model_answer>{{model answer}}</model_answer>

Return only JSON, no other text, with this schema:
{
  "checks": [
    {
      "id": 1,
      "operator": "correctness" | "contradiction",
      "criteria": "<copy the criterion text>",
      "result": "met" | "not_met" | "triggered" | "not_triggered",
      "note": "<short optional note>"
    }
  ],
  "correctness_met": 0,
  "correctness_total": 0,
  "rubric_fraction": 0.0,
  "contradiction_triggered": false,
  "overall": "right" | "wrong" | "abstain",
  "reason": "<one line>"
}
Use "met" or "not_met" only for correctness, and "triggered" or "not_triggered" only for contradiction.
```

## Worked examples

Hypothetical model answers, using real rubrics. Not official Vals grades.

**1) Unit conversion — Q8, `$3.25 Billion`**

Model: “TKO paid $3,250 million at close.”

- Correctness `$3.25 Billion`: `met` ($3,250 million is the same value).
- Contradiction: `not triggered`.
- Fraction: 1/1. Overall: `right`.
- Reason: Equivalent scale; the stated value matches.

If the model had said “about $3.3 billion”: `met` (3.25 rounds to 3.3; no nearby official figure). Overall still `right`. If it had said “about $4 billion”: `not met`. Overall: `wrong`.

**2) Direction and bps — Q9, `140 basis points beat`**

Model: “MU beat Q3 2024 GAAP gross margin guidance by 1.4 percentage points.”

- Correctness: `met` (1.4 pp = 140 bps; direction is beat).
- Contradiction: `not triggered`.
- Fraction: 1/1. Overall: `right`.
- Reason: Equivalent units; beat/miss direction is correct.

If the model had said “missed by 140 bps”: `not met`. Overall: `wrong`. Sign and direction are part of the fact.

**3) Right figure, wrong method — Q10, Palantir 2-year revenue CAGR**

Model: “2024 revenue 2,865,507; 2022 revenue 1,905,871; CAGR = 2,865,507 / 1,905,871 − 1 = 22.6%.”

- `2024 revenue: 2,865,507`: `met`.
- `2022 revenue: 1,905,871`: `met`.
- `2 year revenue CAGR: 22.6%`: `met` (the stated figure is right; the written formula is a simple two-year change, not CAGR).
- Contradiction: `not triggered` (stated values match the official answer).
- Fraction: 3/3. Overall: `right`.
- Reason: Official figures stated; the working shows a wrong formula for CAGR.

**4) Abstain — Q7, `Elinor Mertz is the current CFO of Airbnb`**

Model: “I don’t know who Airbnb’s CFO was as of that date.”

- Correctness: `not met`.
- Contradiction: `not triggered` (no conflicting name).
- Fraction: 0/1. Overall: `abstain`.
- Reason: Refusal with no candidate name.

If the model had said “I believe it was Elinor Mertz, appointed in 2019”: the name is `met`. The 2019 appointment date is outside the official answer, so under this rule it does not trigger contradiction; overall `right`, with the extra claim noted. A different CFO name is `not met`, contradiction `triggered`, overall `wrong`.

**5) Loose match for a date — announcement date**

Model: “The acquisition was announced in December 2023.”

- Correctness `The acquisition was announced on December 18, 2023`: `met`.
- Contradiction: `not triggered`.
- Reason: Month and year still identify the official date.

If the model had said “announced on December 19, 2023”: `not met` (a different day, not a coarser form of the same date).

**6) Loose match for a number, with the clear-mismatch guard**

Model: “The figure was 18.”

- Correctness `18.02`: `met` (integer rounding, and a close value, still shows knowledge of the fact).

Model: “The FY2023 margin was about 8.4%,” when the official FY2023 figure is `8.3%` and FY2024 is `8.4%`:

- Correctness `8.3%`: `met` (within a few percent, and not a clear assignment of the wrong year).

Model: “Netflix ARPU was 11,” when the question involves both `10.82` and `10.91`:

- Correctness `10.82`: `not met` (`11` is closer to the other official figure, `10.91`).
