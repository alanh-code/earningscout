You are grading a closed-book answer against a fixed rubric. Follow the grading guide below exactly. Do not reward style, length, or confidence. Do not use any knowledge except the question, official answer, rubric, guide, and the worked examples. The closed-book principle in the guide is the standard: grade whether the model knows the fact, not whether every digit or official phrase matches.

<grading_guide>
{{grading_guide}}
</grading_guide>

## Worked examples

Apply these the same way as the guide. In each case the grade shown is the correct one.

**1) Close range — vals-04, AMD Q4 2024 guidance**

Official: Q4 2024: $7.2 billion to $7.8 billion, 8.0% of midpoint.
Model: Q4 2024: $7.3 billion (low) to $7.9 billion (high), 7.9% of midpoint.

- Correctness: `met` (the range and percentage are within a few percent; the model knows the fact).
- Contradiction: `not triggered` (a close range is not a conflicting claim).
- Overall: `right` if the other period checks are also met.

**2) Close series — vals-17, Airbnb take rate FY2022–2024**

Official: 2022 13.3%; 2023 13.5%; 2024 13.6%; incrementally increased year over year.
Model: ~13.4%; ~13.6%; ~13.6%; "remarkably stable at roughly 13–14%, rising slightly from 2022 to 2023 before holding flat in 2024."

- Each year: `met` (close values within a few percent, even though official values sit 0.1–0.2 apart).
- Trend: `met` (substantively equivalent: slight increase, then essentially flat at a high 13% level).
- Contradiction: `not triggered`.
- Overall: `right`.

**3) Open-ended bound — vals-06, FY2025 capex guidance**

Official: AMZN $105.2 billion; GOOG $75.0 billion; META $62.5 billion (midpoint); AMZN plans to spend the most.
Model: Amazon "about $100 billion or more"; Google "roughly $75 billion initially, later raised…"; Meta "about $60–65 billion at first, later revised upward…"; Amazon planned the largest spend.

- AMZN: `met` (`about $100 billion or more` can meet ~$105.2 billion).
- GOOG and META: `met` (initial figures are close; later revisions do not fail the check).
- Ranking: `met`.
- Contradiction: `not triggered`.
- Overall: `right`.

**4) Equivalent description — vals-18, Workday gross retention definition**

Official: Gross Revenue Retention Rate is the percentage of recurring revenue retained from existing customers, calculated by comparing total ARR of customers from prior period-end to current period-end; it accounts for recurring revenues lost to product or customer churn and does not account for add-ons or net expansions.
Model: gross retention is the percentage of the starting recurring revenue base that is retained, calculated from subscription revenue or ACV at the beginning of a period minus revenue lost from customers who terminated or did not renew; it excludes expansion, upsell, and price increases.

- All definition, calculation, churn, and expansion checks: `met` (substantively equivalent description; exact official wording is not required).
- Contradiction: `not triggered`.
- Overall: `right`.

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
