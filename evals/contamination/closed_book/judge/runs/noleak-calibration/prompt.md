You are grading a closed-book answer against a fixed rubric. Follow the grading guide below exactly. Do not reward style, length, or confidence. Do not use any knowledge except the question, official answer, rubric, guide, and the worked examples. The closed-book principle in the guide is the standard: grade whether the model knows the fact, not whether every digit or official phrase matches.

<grading_guide>
{{grading_guide}}
</grading_guide>

## Worked examples

Generic illustrations of the closed-book principle. Apply them the same way as the guide. In each case the grade shown is the correct one.

**1) Close range**

Official: FY revenue guidance $4.10 billion to $4.40 billion, 7.1% of midpoint.
Model: $4.20 billion to $4.50 billion, 6.9% of midpoint.

- Correctness: `met` (the range and percentage are within a few percent; the model knows the fact).
- Contradiction: `not triggered` (a close range is not a conflicting claim).

**2) Close values in a tight series**

Official: 2022 8.1%; 2023 8.3%; 2024 8.4%; increased slightly each year.
Model: ~8.2%; ~8.4%; ~8.4%; "stable in the low 8% range, up a little then roughly flat."

- Each year and the trend: `met` (close values within a few percent, even though official values sit 0.1–0.2 apart; the trend wording is substantively equivalent).
- Contradiction: `not triggered`.

**3) Open-ended bound and later revisions**

Official: Company A $52.0 billion; Company B $40.0 billion; Company A plans to spend the most.
Model: Company A "about $50 billion or more"; Company B "roughly $40 billion initially, later raised"; Company A planned the largest spend.

- Both figures and the ranking: `met`. `About $50 billion or more` can meet a figure around $52 billion. Later revisions do not fail the check.
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
