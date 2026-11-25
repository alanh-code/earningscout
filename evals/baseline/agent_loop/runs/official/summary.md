# Agent-loop baseline official

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

n=43. Right 32, wrong 11, abstain 0.
Accuracy 74.4% (32/43), bootstrap 95% CI 60.5–86.0%.

## Cost and usage

Total cost about $2.0021 (agent $1.2184 including tools, judge $0.7837).

| id | type | overall | scored | agent USD | model USD | Exa USD | E2B USD | latency s | turns | tool calls | refused |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| vals-01 | Market Analysis | wrong | yes | $0.0680 | $0.0130 | $0.0550 | $0.0000 | 50.2 | 9 | 16 | 0 |
| vals-02 | Trends | wrong | yes | $0.0222 | $0.0048 | $0.0170 | $0.0004 | 25.1 | 4 | 6 | 0 |
| vals-03 | Beat or Miss | right | yes | $0.0185 | $0.0025 | $0.0160 | $0.0000 | 9.3 | 3 | 4 | 0 |
| vals-04 | Complex Retrieval | right | yes | $0.0189 | $0.0028 | $0.0160 | $0.0001 | 13.2 | 4 | 5 | 0 |
| vals-05 | Simple retrieval - Qualitative | right | yes | $0.0247 | $0.0037 | $0.0210 | $0.0000 | 18.8 | 4 | 6 | 0 |
| vals-06 | Complex Retrieval | wrong | yes | $0.0140 | $0.0020 | $0.0120 | $0.0000 | 8.5 | 3 | 3 | 0 |
| vals-07 | Simple retrieval - Qualitative | right | yes | $0.0091 | $0.0011 | $0.0080 | $0.0000 | 4.0 | 2 | 2 | 0 |
| vals-08 | Simple retrieval - Quantitative | wrong | yes | $0.0340 | $0.0060 | $0.0280 | $0.0000 | 19.1 | 6 | 10 | 0 |
| vals-09 | Beat or Miss | right | yes | $0.0169 | $0.0039 | $0.0130 | $0.0000 | 11.5 | 3 | 4 | 0 |
| vals-10 | Numerical Reasoning | right | yes | $0.0049 | $0.0008 | $0.0040 | $0.0001 | 5.1 | 2 | 2 | 0 |
| vals-12 | Financial Modeling  Projections | wrong | no | $0.0175 | $0.0048 | $0.0120 | $0.0007 | 35.8 | 5 | 6 | 0 |
| vals-13 | Numerical Reasoning | right | yes | $0.0096 | $0.0015 | $0.0080 | $0.0001 | 7.1 | 3 | 3 | 0 |
| vals-14 | Trends | wrong | no | $0.0333 | $0.0071 | $0.0250 | $0.0012 | 46.4 | 6 | 8 | 0 |
| vals-15 | Numerical Reasoning | right | yes | $0.0101 | $0.0020 | $0.0080 | $0.0001 | 10.6 | 3 | 3 | 0 |
| vals-16 | Complex Retrieval | wrong | no | $0.0198 | $0.0048 | $0.0150 | $0.0000 | 17.1 | 4 | 6 | 0 |
| vals-17 | Trends | right | yes | $0.0097 | $0.0016 | $0.0080 | $0.0001 | 8.4 | 3 | 3 | 0 |
| vals-18 | Simple retrieval - Qualitative | right | yes | $0.0264 | $0.0074 | $0.0190 | $0.0000 | 25.7 | 5 | 7 | 0 |
| vals-19 | Numerical Reasoning | right | yes | $0.0184 | $0.0033 | $0.0150 | $0.0001 | 17.4 | 5 | 7 | 0 |
| vals-20 | Numerical Reasoning | right | yes | $0.0096 | $0.0016 | $0.0080 | $0.0000 | 5.2 | 2 | 2 | 0 |
| vals-21 | Simple retrieval - Qualitative | right | yes | $0.0720 | $0.0155 | $0.0540 | $0.0025 | 90.4 | 18 | 27 | 0 |
| vals-22 | Numerical Reasoning | wrong | no | $0.0238 | $0.0035 | $0.0200 | $0.0002 | 12.2 | 5 | 7 | 0 |
| vals-23 | Simple retrieval - Qualitative | wrong | yes | $0.0148 | $0.0018 | $0.0130 | $0.0000 | 8.8 | 3 | 4 | 0 |
| vals-24 | Numerical Reasoning | right | yes | $0.0098 | $0.0018 | $0.0080 | $0.0000 | 8.2 | 2 | 2 | 0 |
| vals-25 | Simple retrieval - Qualitative | wrong | yes | $0.0899 | $0.0217 | $0.0650 | $0.0032 | 109.0 | 17 | 30 | 0 |
| vals-26 | Numerical Reasoning | right | yes | $0.0047 | $0.0007 | $0.0040 | $0.0000 | 4.2 | 2 | 1 | 0 |
| vals-27 | Simple retrieval - Qualitative | right | yes | $0.0419 | $0.0133 | $0.0270 | $0.0016 | 58.4 | 8 | 13 | 0 |
| vals-28 | Simple retrieval - Quantitative | right | yes | $0.0150 | $0.0050 | $0.0100 | $0.0000 | 16.4 | 3 | 4 | 0 |
| vals-29 | Simple retrieval - Qualitative | right | yes | $0.0362 | $0.0092 | $0.0270 | $0.0000 | 29.6 | 6 | 10 | 0 |
| vals-30 | Financial Modeling  Projections | right | yes | $0.0444 | $0.0114 | $0.0310 | $0.0020 | 70.9 | 13 | 18 | 0 |
| vals-31 | Financial Modeling  Projections | right | yes | $0.0101 | $0.0020 | $0.0080 | $0.0001 | 9.1 | 3 | 3 | 0 |
| vals-32 | Simple retrieval - Quantitative | right | yes | $0.0100 | $0.0019 | $0.0080 | $0.0001 | 8.7 | 3 | 3 | 0 |
| vals-33 | Adjustments | wrong | yes | $0.0288 | $0.0074 | $0.0210 | $0.0004 | 42.4 | 6 | 8 | 0 |
| vals-34 | Simple retrieval - Quantitative | right | yes | $0.0093 | $0.0013 | $0.0080 | $0.0000 | 4.5 | 2 | 2 | 0 |
| vals-35 | Adjustments | right | yes | $0.0095 | $0.0015 | $0.0080 | $0.0000 | 5.9 | 2 | 2 | 0 |
| vals-36 | Simple retrieval - Quantitative | right | yes | $0.0137 | $0.0017 | $0.0120 | $0.0000 | 7.9 | 3 | 3 | 0 |
| vals-37 | Simple retrieval - Quantitative | right | yes | $0.0188 | $0.0038 | $0.0140 | $0.0009 | 36.8 | 4 | 6 | 0 |
| vals-38 | Beat or Miss | right | yes | $0.0259 | $0.0072 | $0.0180 | $0.0007 | 35.9 | 5 | 7 | 0 |
| vals-39 | Simple retrieval - Qualitative | right | yes | $0.0274 | $0.0084 | $0.0190 | $0.0000 | 22.4 | 5 | 7 | 0 |
| vals-40 | Adjustments | right | yes | $0.0177 | $0.0047 | $0.0130 | $0.0000 | 24.7 | 3 | 4 | 0 |
| vals-41 | Simple retrieval - Quantitative | right | yes | $0.0092 | $0.0012 | $0.0080 | $0.0000 | 4.1 | 2 | 2 | 0 |
| vals-42 | Market Analysis | wrong | yes | $0.0654 | $0.0144 | $0.0500 | $0.0009 | 53.4 | 8 | 15 | 0 |
| vals-43 | Financial Modeling  Projections | wrong | no | $0.0425 | $0.0142 | $0.0260 | $0.0023 | 91.6 | 9 | 11 | 0 |
| vals-44 | Simple retrieval - Quantitative | right | yes | $0.0206 | $0.0036 | $0.0170 | $0.0000 | 8.7 | 4 | 5 | 0 |
| vals-45 | Adjustments | right | yes | $0.0096 | $0.0016 | $0.0080 | $0.0000 | 6.2 | 2 | 2 | 0 |
| vals-46 | Market Analysis | wrong | yes | $0.0570 | $0.0160 | $0.0410 | $0.0000 | 80.6 | 9 | 14 | 0 |
| vals-47 | Beat or Miss | right | yes | $0.0152 | $0.0021 | $0.0130 | $0.0001 | 8.7 | 4 | 5 | 0 |
| vals-48 | Beat or Miss | wrong | yes | $0.0237 | $0.0057 | $0.0180 | $0.0000 | 27.8 | 5 | 6 | 0 |
| vals-49 | Beat or Miss | wrong | yes | $0.0660 | $0.0130 | $0.0530 | $0.0000 | 64.7 | 9 | 14 | 0 |
