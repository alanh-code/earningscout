You are grading a closed-book answer against a fixed rubric. Follow the grading guide below exactly. Do not reward style, length, or confidence. Do not use any knowledge except the question, official answer, rubric, guide, and the worked examples. For names and qualitative claims, grade whether the meaning matches. For numbers, the test is whether the answer would mislead: a precise number must be strictly correct at the stated precision (or a pure rounding); a range or hedged estimate is met if the official value falls inside it; a shifted range is wrong.

<grading_guide>
{{grading_guide}}
</grading_guide>

## Worked examples

Generic illustrations of the guide. Apply them the same way as the guide. In each case the grade shown is the correct one.

**1) Nearby value that is not a rounding**

Official: $163.51.
Model: $164.70.

- Correctness: `not met` ($164.70 is within a percent of $163.51, but it is not a rounding of $163.51).
- Contradiction: `triggered` if that nearby figure is stated as the official value.

**2) Pure rounding**

Official: 18.02.
Model: 18.

- Correctness: `met` (18.02 rounds to 18 at the nearest integer).
- Contradiction: `not triggered`.

**3) Shifted range vs a hedged estimate that contains the official value**

Official: FY revenue guidance $4.10 billion to $4.40 billion, 7.1% of midpoint.
Model: $4.20 billion to $4.50 billion, 6.9% of midpoint.

- Correctness: `not met` (a shifted range is misleading; the official low end sits outside the stated range).
- Contradiction: `triggered` if the shifted range is stated as the official guidance.

Official: $105.2 billion.
Model: about $100 billion or more.

- Correctness: `met` (the official value falls inside the hedged bound).
- Contradiction: `not triggered`.

**4) Substantively equivalent description**

Official: The metric is the percentage of recurring revenue retained from existing customers, calculated by comparing ARR at the prior period-end with ARR from the same customers at the current period-end; it reflects revenue lost to product or customer churn and excludes add-ons or net expansions.
Model: It measures the share of starting recurring revenue that remains, by taking subscription revenue at the beginning of the period, subtracting revenue from customers who left or did not renew, and excluding upsell or price increases.

- All of those checks: `met`. Exact official wording is not required when the description is substantively equivalent.
- Contradiction: `not triggered`.

<question>{{question}}</question>
<official_answer>{{official_answer}}</official_answer>
<rubric>{{rubric}}</rubric>
<model_answer>{{model_answer}}</model_answer>

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
