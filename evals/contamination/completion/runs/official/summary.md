# Completion test run official

Model `claude-sonnet-5-5`, 200 requests, all passed the closed environment checks. Shown: first 40% of each question. Tokens: 17840 in, 9644 out. Cost about $0.13.

Score: embedding cosine similarity, `all-mpnet-base-v2`, sentence-transformers 6.2.0.

| Group | Mode | n | Mean | Median | Min | Max |
|---|---|---|---|---|---|---|
| vals | guided | 50 | 0.51 | 0.50 | 0.23 | 0.81 |
| vals | general | 50 | 0.44 | 0.42 | 0.09 | 0.82 |
| control | guided | 50 | 0.53 | 0.55 | 0.14 | 0.87 |
| control | general | 50 | 0.54 | 0.56 | 0.13 | 0.86 |

Guided above general on 60 of 100 questions.

Highest similarity, Vals questions (* = one of the 10 selected questions):

* vals-12 general 0.82: real "to the average growth rate in March over the past 3 years, will TSM beat or miss Q1 2025 guidance and by how much? Show your work, including Q1 guidance, historical March growth rates, average growth, and projected implied Q1 revenue.", model "to its average month-over-month growth rate observed in January and February 2025, what will TSM's total revenue for Q1 2025 be, and how does it compare to the company's Q1 guidance range?"
* vals-01 * guided 0.81: real "merger with Nippon Steel and its effect on its business operations?", model "mergers and acquisitions strategy in its recent financial filings, including any discussion of the proposed transaction with Nippon Steel and the associated regulatory risks?"
* vals-40 guided 0.79: real "make to its Net Income to Derive Adjusted EBITDA?", model "make to its net income to arrive at adjusted EBITDA, and how have these adjustments changed over the past few fiscal years?"
* vals-41 general 0.79: real "sales growth in Q4 2024?", model "sales growth in the most recent quarter?"
* vals-40 general 0.78: real "make to its Net Income to Derive Adjusted EBITDA?", model "make to its EBITDA calculation to arrive at Adjusted EBITDA, and how does this metric differ from traditional EBITDA?"
* vals-44 * guided 0.78: real "per Booking for Airbnb (NASDAQ: ABNB) in the Asia Pacific region?", model "per Stay for Airbnb, Inc. (ABNB) reported in its annual 10-K filing?"
* vals-12 guided 0.76: real "to the average growth rate in March over the past 3 years, will TSM beat or miss Q1 2025 guidance and by how much? Show your work, including Q1 guidance, historical March growth rates, average growth, and projected implied Q1 revenue.", model "to the average month-over-month growth rate observed in the previous three months (December 2024, January 2025, and February 2025), what would be TSM's estimated total revenue for the first quarter of 2025 in NT$ billions? Use the monthly revenue figures reported by TSMC and round your answer to the nearest whole number."
* vals-41 guided 0.76: real "sales growth in Q4 2024?", model "sales growth for the most recent fiscal quarter?"
* vals-01 * general 0.76: real "merger with Nippon Steel and its effect on its business operations?", model "investments in new steelmaking technology and capacity, particularly following its acquisition by Nippon Steel, and what impact are those commitments expected to have on its workforce and domestic operations?"
* vals-32 general 0.75: real "loan originations between purchases and refinancings for the last 9 months as of 11/12/2024?", model "its originations between purchase and refinance loans, and how has that mix changed year over year?"
