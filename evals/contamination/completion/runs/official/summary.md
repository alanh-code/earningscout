# Completion test run official

Model `deepseek-flash`, thinking off, temperature 0, seed 42. 200 requests, all passed the closed environment checks. Shown: first 60% of each question. Tokens: 14572 in, 3129 out. Cost about $0.0041.

Score: embedding cosine similarity, `all-mpnet-base-v2`, sentence-transformers 6.2.0.

| Group | Mode | n | Mean | Median | Min | Max |
|---|---|---|---|---|---|---|
| vals | guided | 50 | 0.49 | 0.47 | 0.03 | 0.94 |
| vals | general | 50 | 0.44 | 0.46 | -0.06 | 0.92 |
| control | guided | 50 | 0.48 | 0.50 | 0.06 | 0.83 |
| control | general | 50 | 0.47 | 0.48 | 0.03 | 0.99 |

Guided above general on 49 of 100 questions.

Highest similarity, Vals questions (* = one of the 10 selected questions):

* vals-07 guided 0.94: real "as of April 07, 2025?", model "as of December 31, 2024?"
* vals-41 general 0.92: real "growth in Q4 2024?", model "growth in the third quarter of 2024?"
* vals-06 guided 0.91: real "the most in capex in 2025?", model "the most on capital expenditures in 2025?"
* vals-06 general 0.91: real "the most in capex in 2025?", model "the most on capital expenditures in 2025?"
* vals-07 general 0.90: real "as of April 07, 2025?", model "as of 2024?"
* vals-33 * general 0.81: real "in 2024 were refinanced at 3% higher interest rates than current?", model "were refinanced at a lower interest rate?"
* vals-17 * general 0.80: real "year on a separate line and provide a brief one sentence comment on the trend.", model "year and explain the key drivers behind the trend."
* vals-32 guided 0.80: real "refinancings for the last 9 months as of 11/12/2024?", model "refinances for Q2 2024? Please provide the dollar amounts and percentages for each category."
* vals-17 * guided 0.79: real "year on a separate line and provide a brief one sentence comment on the trend.", model "year, and explain the primary factors driving the trend."
* vals-29 guided 0.70: real "2024. Provide the KPI and FY 2024 Total.", model "2023, along with their reported values for that fiscal year."
