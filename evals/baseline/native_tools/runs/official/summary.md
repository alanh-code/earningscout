# Native-tools baseline official

Model `claude-sonnet-5-5` with built-in server tools, 50 questions from `data/vals/public.csv`.
Judge: `claude-opus-5-5`, `judge_prompt_strict.md`, 3 passes, majority vote.
Protocol as-of date: Thursday, May 1, 2025. It is injected into the system prompt when the question contains "current"; a date given in the question takes precedence.
Accuracy is scored on 48 questions after excluding 2 listed in `evals/baseline/excluded_questions.csv`. Run data for excluded questions is kept.

## Tools

Enabled: {"web_search": "web_search_20260318", "web_fetch": "web_fetch_20260318", "code_execution": "code_execution_20260521", "thinking": "adaptive (Sonnet 5.5 default, effort high)", "blocked_domains": ["github.com", "githubusercontent.com", "raw.githubusercontent.com", "vals.ai", "huggingface.co", "hf.co", "zenodo.org", "hf-mirror.com"]}
Unavailable (not used): computer_toolset_20260801 and browser_toolset_20260801 (client tools; need a local executor); memory, bash, and text_editor (client tools); advisor_20260301 (beta; not a general research tool for this run); tool_search (for deferred tool loading; not needed here)

## Accuracy

n=48. Right 26, wrong 22, abstain 0.
Accuracy 54.2% (26/48), bootstrap 95% CI 39.6–68.8%.

By question type:

| Type | n | Right | Wrong | Abstain | Accuracy |
|---|---:|---:|---:|---:|---:|
| Adjustments | 4 | 2 | 2 | 0 | 50.0% |
| Beat or Miss | 6 | 2 | 4 | 0 | 33.3% |
| Complex Retrieval | 3 | 1 | 2 | 0 | 33.3% |
| Financial Modeling  Projections | 4 | 1 | 3 | 0 | 25.0% |
| Market Analysis | 3 | 0 | 3 | 0 | 0.0% |
| Numerical Reasoning | 8 | 6 | 2 | 0 | 75.0% |
| Simple retrieval - Qualitative | 9 | 6 | 3 | 0 | 66.7% |
| Simple retrieval - Quantitative | 8 | 7 | 1 | 0 | 87.5% |
| Trends | 3 | 1 | 2 | 0 | 33.3% |

## Excluded questions

These ids are kept in the run data and in the table below but are not scored.

| id | type | overall | reason |
|---|---|---|---|
| vals-11 | Simple retrieval - Quantitative | wrong | answer depends on an unstated relative time period |
| vals-50 | Beat or Miss | wrong | answer depends on an unstated relative time period |

## Cost and usage

Total cost about $17.0193 (agent $9.6012, judge $7.4181).
Median latency 24.9s. Average tool calls 9.22.

| id | type | overall | scored | agent USD | latency s | tool calls | stop |
|---|---|---|---|---:|---:|---:|---|
| vals-01 | Market Analysis | wrong | yes | $0.1338 | 19.1 | 6 | end_turn |
| vals-02 | Trends | wrong | yes | $0.1451 | 25.0 | 7 | end_turn |
| vals-03 | Beat or Miss | wrong | yes | $0.1004 | 16.9 | 5 | end_turn |
| vals-04 | Complex Retrieval | right | yes | $0.0220 | 6.0 | 0 | end_turn |
| vals-05 | Simple retrieval - Qualitative | right | yes | $0.3699 | 112.9 | 18 | end_turn |
| vals-06 | Complex Retrieval | wrong | yes | $0.1305 | 14.4 | 7 | end_turn |
| vals-07 | Simple retrieval - Qualitative | right | yes | $0.0600 | 25.5 | 3 | end_turn |
| vals-08 | Simple retrieval - Quantitative | wrong | yes | $0.1818 | 31.7 | 10 | end_turn |
| vals-09 | Beat or Miss | right | yes | $0.1251 | 21.4 | 6 | end_turn |
| vals-10 | Numerical Reasoning | wrong | yes | $0.0196 | 4.1 | 0 | end_turn |
| vals-11 | Simple retrieval - Quantitative | wrong | no | $0.1410 | 25.6 | 10 | end_turn |
| vals-12 | Financial Modeling  Projections | wrong | yes | $0.1863 | 25.6 | 9 | end_turn |
| vals-13 | Numerical Reasoning | right | yes | $0.1277 | 20.9 | 7 | end_turn |
| vals-14 | Trends | wrong | yes | $0.2089 | 35.1 | 11 | end_turn |
| vals-15 | Numerical Reasoning | right | yes | $0.0893 | 14.6 | 4 | end_turn |
| vals-16 | Complex Retrieval | wrong | yes | $0.7496 | 77.5 | 24 | end_turn |
| vals-17 | Trends | right | yes | $0.3658 | 102.0 | 22 | end_turn |
| vals-18 | Simple retrieval - Qualitative | right | yes | $0.1314 | 18.8 | 6 | end_turn |
| vals-19 | Numerical Reasoning | right | yes | $0.1979 | 31.0 | 10 | end_turn |
| vals-20 | Numerical Reasoning | right | yes | $0.0851 | 14.7 | 4 | end_turn |
| vals-21 | Simple retrieval - Qualitative | right | yes | $0.1037 | 38.8 | 5 | end_turn |
| vals-22 | Numerical Reasoning | wrong | yes | $0.1624 | 26.3 | 8 | end_turn |
| vals-23 | Simple retrieval - Qualitative | right | yes | $0.1415 | 22.2 | 7 | end_turn |
| vals-24 | Numerical Reasoning | right | yes | $0.1099 | 40.2 | 5 | end_turn |
| vals-25 | Simple retrieval - Qualitative | wrong | yes | $0.1880 | 66.3 | 9 | end_turn |
| vals-26 | Numerical Reasoning | right | yes | $0.0641 | 9.9 | 3 | end_turn |
| vals-27 | Simple retrieval - Qualitative | wrong | yes | $0.1221 | 17.5 | 6 | end_turn |
| vals-28 | Simple retrieval - Quantitative | right | yes | $0.0871 | 12.9 | 4 | end_turn |
| vals-29 | Simple retrieval - Qualitative | right | yes | $0.1756 | 22.1 | 10 | end_turn |
| vals-30 | Financial Modeling  Projections | right | yes | $0.2128 | 24.8 | 8 | end_turn |
| vals-31 | Financial Modeling  Projections | wrong | yes | $0.1750 | 67.3 | 9 | end_turn |
| vals-32 | Simple retrieval - Quantitative | right | yes | $0.1128 | 19.2 | 6 | end_turn |
| vals-33 | Adjustments | wrong | yes | $0.1305 | 30.6 | 6 | end_turn |
| vals-34 | Simple retrieval - Quantitative | right | yes | $0.1201 | 14.0 | 6 | end_turn |
| vals-35 | Adjustments | right | yes | $0.2340 | 39.8 | 14 | end_turn |
| vals-36 | Simple retrieval - Quantitative | right | yes | $0.1074 | 13.7 | 5 | end_turn |
| vals-37 | Simple retrieval - Quantitative | right | yes | $0.2194 | 29.7 | 10 | end_turn |
| vals-38 | Beat or Miss | wrong | yes | $0.3102 | 41.9 | 15 | end_turn |
| vals-39 | Simple retrieval - Qualitative | wrong | yes | $0.0948 | 19.9 | 4 | end_turn |
| vals-40 | Adjustments | wrong | yes | $0.1001 | 18.9 | 5 | end_turn |
| vals-41 | Simple retrieval - Quantitative | right | yes | $0.1153 | 16.3 | 6 | end_turn |
| vals-42 | Market Analysis | wrong | yes | $0.9397 | 106.1 | 35 | end_turn |
| vals-43 | Financial Modeling  Projections | wrong | yes | $0.1503 | 24.1 | 7 | end_turn |
| vals-44 | Simple retrieval - Quantitative | right | yes | $0.0849 | 10.0 | 4 | end_turn |
| vals-45 | Adjustments | right | yes | $0.1227 | 14.9 | 6 | end_turn |
| vals-46 | Market Analysis | wrong | yes | $0.4246 | 82.3 | 17 | end_turn |
| vals-47 | Beat or Miss | right | yes | $0.2804 | 51.4 | 12 | end_turn |
| vals-48 | Beat or Miss | wrong | yes | $0.1989 | 30.9 | 11 | end_turn |
| vals-49 | Beat or Miss | wrong | yes | $0.4970 | 65.7 | 33 | end_turn |
| vals-50 | Beat or Miss | wrong | no | $0.2452 | 46.6 | 16 | end_turn |
