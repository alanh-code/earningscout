# Agent-loop baseline repeat_2

Agent `deepseek-flash` (DeepSeek-V4.1-Flash) in the tool loop from `agent/`, 48 questions from `data/vals/public.csv`.
Judge: `deepseek-v4-pro`, `judge_prompt_strict.md`, 3 passes, majority vote.
Protocol as-of date: Thursday, May 1, 2025. It is injected into the system prompt when the question contains "current"; a date given in the question takes precedence.
Accuracy is scored on 43 questions; 5 answered questions are excluded (`evals/baseline/excluded_questions.csv`).
Models reported by the API: agent deepseek-flash; judge deepseek-v4-pro.

## Tools

* `web_search`: Exa /search type=lite, 8 results, highlights, endPublishedDate=2025-05-01T23:59:59.999Z
* `web_fetch`: Exa /contents text up to 40000 chars, host check before and after
* `code_execution`: E2B code interpreter, internet off, 120s per call, 900s lifetime, killed after each question
* Blocked hosts (search, fetch; the sandbox has no internet): github.com, githubusercontent.com, raw.githubusercontent.com, vals.ai, huggingface.co, hf.co, zenodo.org, hf-mirror.com, vals-ai.com, github.laiyagushi.com, deepwiki.com, meridianlabs-ai.github.io, harborframework.com, openreward.ai, context7.com, shadowgraph.io, doi.org/10.5281, doi.org/10.57967, cdn.jsdelivr.net/gh, fastly.jsdelivr.net/gh, gcore.jsdelivr.net/gh, testingcf.jsdelivr.net/gh, cdn.statically.io/gh, githack.com, ghproxy.net, ghproxy.com, gh-proxy.com, ghfast.top, kkgithub.com, bgithub.xyz, gitmirror.com, verified-skill.com, coralbricks.ai
* Budgets per question: {"web_search": 15, "web_fetch": 15, "code_execution": 30}; turn limit 40.

## Accuracy

n=43. Right 31, wrong 12, abstain 0.
Accuracy 72.1% (31/43), bootstrap 95% CI 58.1–86.0%.

## Cost and usage

Total cost about $2.2001 (agent $1.3725 including tools, judge $0.8277).

| id | type | overall | scored | agent USD | model USD | Exa USD | E2B USD | latency s | turns | tool calls | refused |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| vals-01 | Market Analysis | wrong | yes | $0.0380 | $0.0100 | $0.0280 | $0.0000 | 34.4 | 6 | 10 | 0 |
| vals-02 | Trends | wrong | yes | $0.0497 | $0.0133 | $0.0360 | $0.0004 | 54.4 | 10 | 16 | 0 |
| vals-03 | Beat or Miss | right | yes | $0.0164 | $0.0034 | $0.0130 | $0.0000 | 12.0 | 3 | 4 | 0 |
| vals-04 | Complex Retrieval | right | yes | $0.0179 | $0.0018 | $0.0160 | $0.0001 | 10.8 | 4 | 5 | 0 |
| vals-05 | Simple retrieval - Qualitative | right | yes | $0.0556 | $0.0086 | $0.0470 | $0.0000 | 41.2 | 8 | 14 | 0 |
| vals-06 | Complex Retrieval | wrong | yes | $0.0226 | $0.0026 | $0.0200 | $0.0000 | 9.5 | 3 | 5 | 0 |
| vals-07 | Simple retrieval - Qualitative | right | yes | $0.0047 | $0.0007 | $0.0040 | $0.0000 | 3.1 | 2 | 1 | 0 |
| vals-08 | Simple retrieval - Quantitative | wrong | yes | $0.0364 | $0.0084 | $0.0270 | $0.0010 | 40.1 | 6 | 10 | 0 |
| vals-09 | Beat or Miss | right | yes | $0.0097 | $0.0017 | $0.0080 | $0.0000 | 9.4 | 2 | 2 | 0 |
| vals-10 | Numerical Reasoning | right | yes | $0.0049 | $0.0009 | $0.0040 | $0.0001 | 4.3 | 2 | 2 | 0 |
| vals-12 | Financial Modeling  Projections | wrong | no | $0.0178 | $0.0054 | $0.0120 | $0.0003 | 44.3 | 5 | 7 | 0 |
| vals-13 | Numerical Reasoning | right | yes | $0.0188 | $0.0056 | $0.0120 | $0.0012 | 44.3 | 8 | 9 | 0 |
| vals-14 | Trends | wrong | no | $0.0104 | $0.0022 | $0.0080 | $0.0001 | 8.4 | 3 | 3 | 0 |
| vals-15 | Numerical Reasoning | right | yes | $0.0186 | $0.0065 | $0.0120 | $0.0001 | 11.8 | 5 | 7 | 0 |
| vals-16 | Complex Retrieval | wrong | no | $0.0265 | $0.0065 | $0.0200 | $0.0000 | 22.1 | 5 | 8 | 0 |
| vals-17 | Trends | right | yes | $0.0146 | $0.0024 | $0.0120 | $0.0002 | 11.0 | 3 | 4 | 0 |
| vals-18 | Simple retrieval - Qualitative | right | yes | $0.0505 | $0.0129 | $0.0360 | $0.0017 | 60.0 | 12 | 20 | 0 |
| vals-19 | Numerical Reasoning | right | yes | $0.0183 | $0.0032 | $0.0150 | $0.0001 | 15.7 | 5 | 7 | 0 |
| vals-20 | Numerical Reasoning | right | yes | $0.0049 | $0.0009 | $0.0040 | $0.0000 | 5.8 | 2 | 1 | 0 |
| vals-21 | Simple retrieval - Qualitative | right | yes | $0.0591 | $0.0161 | $0.0430 | $0.0000 | 86.1 | 15 | 23 | 0 |
| vals-22 | Numerical Reasoning | wrong | no | $0.0619 | $0.0138 | $0.0470 | $0.0011 | 40.7 | 10 | 20 | 0 |
| vals-23 | Simple retrieval - Qualitative | right | yes | $0.0243 | $0.0033 | $0.0210 | $0.0000 | 13.3 | 4 | 6 | 0 |
| vals-24 | Numerical Reasoning | right | yes | $0.0128 | $0.0036 | $0.0090 | $0.0002 | 13.3 | 3 | 4 | 0 |
| vals-25 | Simple retrieval - Qualitative | wrong | yes | $0.0771 | $0.0237 | $0.0510 | $0.0025 | 133.9 | 16 | 27 | 0 |
| vals-26 | Numerical Reasoning | right | yes | $0.0090 | $0.0009 | $0.0080 | $0.0000 | 5.8 | 3 | 3 | 0 |
| vals-27 | Simple retrieval - Qualitative | right | yes | $0.0938 | $0.0238 | $0.0700 | $0.0000 | 88.8 | 15 | 26 | 0 |
| vals-28 | Simple retrieval - Quantitative | right | yes | $0.0232 | $0.0052 | $0.0180 | $0.0000 | 21.1 | 4 | 6 | 0 |
| vals-29 | Simple retrieval - Qualitative | right | yes | $0.0424 | $0.0114 | $0.0310 | $0.0000 | 33.5 | 8 | 13 | 0 |
| vals-30 | Financial Modeling  Projections | right | yes | $0.0539 | $0.0119 | $0.0420 | $0.0000 | 41.5 | 9 | 15 | 0 |
| vals-31 | Financial Modeling  Projections | right | yes | $0.0101 | $0.0020 | $0.0080 | $0.0001 | 8.0 | 3 | 3 | 0 |
| vals-32 | Simple retrieval - Quantitative | right | yes | $0.0099 | $0.0018 | $0.0080 | $0.0001 | 8.2 | 3 | 3 | 0 |
| vals-33 | Adjustments | wrong | yes | $0.0457 | $0.0146 | $0.0310 | $0.0002 | 53.2 | 12 | 17 | 0 |
| vals-34 | Simple retrieval - Quantitative | right | yes | $0.0092 | $0.0012 | $0.0080 | $0.0000 | 3.6 | 2 | 2 | 0 |
| vals-35 | Adjustments | right | yes | $0.0048 | $0.0008 | $0.0040 | $0.0000 | 5.8 | 2 | 1 | 0 |
| vals-36 | Simple retrieval - Quantitative | wrong | yes | $0.0271 | $0.0049 | $0.0220 | $0.0002 | 20.6 | 5 | 8 | 0 |
| vals-37 | Simple retrieval - Quantitative | right | yes | $0.0122 | $0.0031 | $0.0090 | $0.0001 | 8.7 | 3 | 4 | 0 |
| vals-38 | Beat or Miss | right | yes | $0.0106 | $0.0023 | $0.0080 | $0.0002 | 14.8 | 3 | 3 | 0 |
| vals-39 | Simple retrieval - Qualitative | right | yes | $0.0248 | $0.0068 | $0.0180 | $0.0000 | 19.8 | 4 | 6 | 0 |
| vals-40 | Adjustments | wrong | yes | $0.0258 | $0.0078 | $0.0180 | $0.0000 | 27.9 | 5 | 6 | 0 |
| vals-41 | Simple retrieval - Quantitative | right | yes | $0.0092 | $0.0012 | $0.0080 | $0.0000 | 4.7 | 2 | 2 | 0 |
| vals-42 | Market Analysis | wrong | yes | $0.0484 | $0.0204 | $0.0280 | $0.0000 | 57.1 | 7 | 14 | 0 |
| vals-43 | Financial Modeling  Projections | wrong | no | $0.0530 | $0.0167 | $0.0340 | $0.0023 | 95.2 | 10 | 13 | 0 |
| vals-44 | Simple retrieval - Quantitative | right | yes | $0.0205 | $0.0035 | $0.0170 | $0.0000 | 8.3 | 4 | 5 | 0 |
| vals-45 | Adjustments | right | yes | $0.0096 | $0.0016 | $0.0080 | $0.0000 | 4.6 | 2 | 2 | 0 |
| vals-46 | Market Analysis | wrong | yes | $0.0723 | $0.0211 | $0.0490 | $0.0022 | 118.3 | 11 | 17 | 0 |
| vals-47 | Beat or Miss | right | yes | $0.0274 | $0.0072 | $0.0200 | $0.0003 | 24.8 | 6 | 9 | 0 |
| vals-48 | Beat or Miss | wrong | yes | $0.0198 | $0.0048 | $0.0150 | $0.0000 | 22.1 | 5 | 6 | 0 |
| vals-49 | Beat or Miss | wrong | yes | $0.0382 | $0.0112 | $0.0270 | $0.0000 | 36.5 | 6 | 9 | 0 |
