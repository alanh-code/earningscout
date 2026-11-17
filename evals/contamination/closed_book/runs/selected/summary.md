# Closed-book run selected

Model `claude-sonnet-5-5`, 10 questions, one fresh request each.
No tools, no system prompt, no files. User message was only the question text.
All 10 responses passed the closed-environment checks.
Tokens: 595 in, 4418 out. Cost about $0.0454 at $2.00/$10.00 per million input/output tokens.

Grades are in `results.md` (strict 3-pass Opus majority; no human grades).

| id | type | stop_reason | input tokens | output tokens | cost USD |
|---|---|---|---|---|---|
| vals-01 | Market Analysis | end_turn | 38 | 550 | $0.005576 |
| vals-03 | Beat or Miss | end_turn | 47 | 277 | $0.002864 |
| vals-11 | Simple retrieval - Quantitative | end_turn | 39 | 209 | $0.002168 |
| vals-16 | Complex Retrieval | end_turn | 97 | 490 | $0.005094 |
| vals-17 | Trends | end_turn | 87 | 288 | $0.003054 |
| vals-18 | Simple retrieval - Qualitative | end_turn | 55 | 530 | $0.005410 |
| vals-19 | Numerical Reasoning | end_turn | 57 | 421 | $0.004324 |
| vals-31 | Financial Modeling  Projections | end_turn | 68 | 535 | $0.005486 |
| vals-33 | Adjustments | end_turn | 54 | 710 | $0.007208 |
| vals-44 | Simple retrieval - Quantitative | end_turn | 53 | 408 | $0.004186 |
