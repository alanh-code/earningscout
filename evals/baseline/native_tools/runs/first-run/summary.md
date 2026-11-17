# Native-tools baseline first-run

Model `claude-sonnet-5-5` with built-in server tools, 50 questions from `data/vals/public.csv`.
Judge: `claude-opus-5-5`, `judge_prompt_strict.md`, 3 passes, majority vote.
Protocol as-of date: Thursday, May 1, 2025. It is injected into the system prompt when the question contains "current"; a date given in the question takes precedence.
Accuracy is scored on 48 questions after excluding 2 listed in `evals/baseline/excluded_questions.csv`. Run data for excluded questions is kept.

## Tools

Enabled: {"web_search": "web_search_20260318", "web_fetch": "web_fetch_20260318", "code_execution": "code_execution_20260521", "thinking": "adaptive (Sonnet 5.5 default, effort high)"}
Unavailable (not used): computer_toolset_20260801 and browser_toolset_20260801 (client tools; need a local executor); memory, bash, and text_editor (client tools); advisor_20260301 (beta; not a general research tool for this run); tool_search (for deferred tool loading; not needed here)

## Accuracy

n=48. Right 27, wrong 21, abstain 0.
Accuracy 56.2% (27/48), bootstrap 95% CI 41.7–70.8%.

By question type:

| Type | n | Right | Wrong | Abstain | Accuracy |
|---|---:|---:|---:|---:|---:|
| Adjustments | 4 | 2 | 2 | 0 | 50.0% |
| Beat or Miss | 6 | 3 | 3 | 0 | 50.0% |
| Complex Retrieval | 3 | 1 | 2 | 0 | 33.3% |
| Financial Modeling  Projections | 4 | 1 | 3 | 0 | 25.0% |
| Market Analysis | 3 | 0 | 3 | 0 | 0.0% |
| Numerical Reasoning | 8 | 7 | 1 | 0 | 87.5% |
| Simple retrieval - Qualitative | 9 | 6 | 3 | 0 | 66.7% |
| Simple retrieval - Quantitative | 8 | 6 | 2 | 0 | 75.0% |
| Trends | 3 | 1 | 2 | 0 | 33.3% |

## Excluded questions

These ids are kept in the run data and in the table below but are not scored.

| id | type | overall | reason |
|---|---|---|---|
| vals-11 | Simple retrieval - Quantitative | wrong | answer depends on an unstated relative time period |
| vals-50 | Beat or Miss | wrong | answer depends on an unstated relative time period |

## Cost and usage

Total cost about $16.4108 (agent $8.9728, judge $7.4380).
Median latency 22.3s. Average tool calls 8.38.

| id | type | overall | scored | agent USD | latency s | tool calls | stop |
|---|---|---|---|---:|---:|---:|---|
| vals-01 | Market Analysis | wrong | yes | $0.1730 | 114.3 | 9 | end_turn |
| vals-02 | Trends | wrong | yes | $0.1193 | 19.2 | 6 | end_turn |
| vals-03 | Beat or Miss | right | yes | $0.1092 | 19.2 | 5 | end_turn |
| vals-04 | Complex Retrieval | right | yes | $0.0227 | 6.2 | 0 | end_turn |
| vals-05 | Simple retrieval - Qualitative | right | yes | $0.1746 | 22.3 | 9 | end_turn |
| vals-06 | Complex Retrieval | wrong | yes | $0.1188 | 12.2 | 7 | end_turn |
| vals-07 | Simple retrieval - Qualitative | right | yes | $0.0598 | 8.8 | 3 | end_turn |
| vals-08 | Simple retrieval - Quantitative | wrong | yes | $0.1482 | 28.3 | 8 | end_turn |
| vals-09 | Beat or Miss | right | yes | $0.1783 | 22.6 | 9 | end_turn |
| vals-10 | Numerical Reasoning | right | yes | $0.0193 | 4.0 | 0 | end_turn |
| vals-11 | Simple retrieval - Quantitative | wrong | no | $0.1404 | 17.1 | 8 | end_turn |
| vals-12 | Financial Modeling  Projections | wrong | yes | $0.1623 | 26.1 | 8 | end_turn |
| vals-13 | Numerical Reasoning | right | yes | $0.1461 | 22.2 | 8 | end_turn |
| vals-14 | Trends | wrong | yes | $0.2861 | 35.6 | 14 | end_turn |
| vals-15 | Numerical Reasoning | right | yes | $0.0968 | 12.9 | 5 | end_turn |
| vals-16 | Complex Retrieval | wrong | yes | $0.3405 | 134.0 | 13 | end_turn |
| vals-17 | Trends | right | yes | $0.3078 | 53.8 | 15 | end_turn |
| vals-18 | Simple retrieval - Qualitative | right | yes | $0.1818 | 21.7 | 8 | end_turn |
| vals-19 | Numerical Reasoning | right | yes | $0.2201 | 29.8 | 11 | end_turn |
| vals-20 | Numerical Reasoning | right | yes | $0.0651 | 11.3 | 3 | end_turn |
| vals-21 | Simple retrieval - Qualitative | right | yes | $0.1027 | 16.7 | 5 | end_turn |
| vals-22 | Numerical Reasoning | wrong | yes | $0.1646 | 23.3 | 8 | end_turn |
| vals-23 | Simple retrieval - Qualitative | right | yes | $0.0965 | 15.1 | 5 | end_turn |
| vals-24 | Numerical Reasoning | right | yes | $0.1424 | 22.7 | 8 | end_turn |
| vals-25 | Simple retrieval - Qualitative | wrong | yes | $0.2307 | 30.9 | 10 | end_turn |
| vals-26 | Numerical Reasoning | right | yes | $0.0644 | 9.3 | 3 | end_turn |
| vals-27 | Simple retrieval - Qualitative | wrong | yes | $0.1279 | 18.6 | 6 | end_turn |
| vals-28 | Simple retrieval - Quantitative | right | yes | $0.0838 | 13.0 | 4 | end_turn |
| vals-29 | Simple retrieval - Qualitative | right | yes | $0.2046 | 27.4 | 12 | end_turn |
| vals-30 | Financial Modeling  Projections | right | yes | $0.3449 | 37.8 | 12 | end_turn |
| vals-31 | Financial Modeling  Projections | wrong | yes | $0.1255 | 23.0 | 6 | end_turn |
| vals-32 | Simple retrieval - Quantitative | right | yes | $0.1075 | 18.4 | 6 | end_turn |
| vals-33 | Adjustments | wrong | yes | $0.1429 | 20.5 | 6 | end_turn |
| vals-34 | Simple retrieval - Quantitative | right | yes | $0.2035 | 26.8 | 11 | end_turn |
| vals-35 | Adjustments | wrong | yes | $0.0247 | 9.2 | 0 | end_turn |
| vals-36 | Simple retrieval - Quantitative | wrong | yes | $0.0832 | 11.1 | 4 | end_turn |
| vals-37 | Simple retrieval - Quantitative | right | yes | $0.1115 | 17.8 | 5 | end_turn |
| vals-38 | Beat or Miss | wrong | yes | $0.2221 | 28.4 | 11 | end_turn |
| vals-39 | Simple retrieval - Qualitative | wrong | yes | $0.2014 | 26.3 | 10 | end_turn |
| vals-40 | Adjustments | right | yes | $0.1906 | 29.6 | 9 | end_turn |
| vals-41 | Simple retrieval - Quantitative | right | yes | $0.0964 | 13.5 | 5 | end_turn |
| vals-42 | Market Analysis | wrong | yes | $0.6817 | 74.3 | 22 | end_turn |
| vals-43 | Financial Modeling  Projections | wrong | yes | $0.1254 | 21.4 | 6 | end_turn |
| vals-44 | Simple retrieval - Quantitative | right | yes | $0.0917 | 10.2 | 4 | end_turn |
| vals-45 | Adjustments | right | yes | $0.0846 | 9.4 | 4 | end_turn |
| vals-46 | Market Analysis | wrong | yes | $0.1648 | 25.8 | 8 | end_turn |
| vals-47 | Beat or Miss | right | yes | $0.5138 | 49.6 | 20 | end_turn |
| vals-48 | Beat or Miss | wrong | yes | $0.3311 | 41.5 | 15 | end_turn |
| vals-49 | Beat or Miss | wrong | yes | $0.4958 | 62.3 | 25 | end_turn |
| vals-50 | Beat or Miss | wrong | no | $0.3418 | 43.2 | 20 | end_turn |
