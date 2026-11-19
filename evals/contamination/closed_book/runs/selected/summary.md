# Closed-book run selected

Model `deepseek-flash`, 10 questions, one fresh request each.
No tools, no system prompt, no files. User message was only the question text. Thinking off, temperature 0, seed 42.
All 10 responses passed the closed-environment checks.
Tokens: 388 in, 2924 out. Cost about $0.0018 at $0.150/$0.60 per million input/output tokens, cached input $0.003/M (deepseek-flash off-peak list price; peak is 2x).

This file has no grades.

| id | type | stop_reason | input tokens | output tokens | cost USD |
|---|---|---|---|---|---|
| vals-01 | Market Analysis | stop | 25 | 495 | $0.000301 |
| vals-03 | Beat or Miss | stop | 28 | 75 | $0.000049 |
| vals-11 | Simple retrieval - Quantitative | stop | 28 | 35 | $0.000025 |
| vals-16 | Complex Retrieval | stop | 60 | 371 | $0.000232 |
| vals-17 | Trends | stop | 54 | 121 | $0.000081 |
| vals-18 | Simple retrieval - Qualitative | stop | 33 | 452 | $0.000276 |
| vals-19 | Numerical Reasoning | stop | 46 | 295 | $0.000184 |
| vals-31 | Financial Modeling  Projections | stop | 45 | 365 | $0.000226 |
| vals-33 | Adjustments | stop | 38 | 682 | $0.000415 |
| vals-44 | Simple retrieval - Quantitative | stop | 31 | 33 | $0.000024 |
