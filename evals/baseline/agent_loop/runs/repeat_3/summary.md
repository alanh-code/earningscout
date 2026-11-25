# Agent-loop baseline repeat_3

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

n=43. Right 30, wrong 13, abstain 0.
Accuracy 69.8% (30/43), bootstrap 95% CI 55.8–83.7%.

## Cost and usage

Total cost about $2.0243 (agent $1.3002 including tools, judge $0.7241).

| id | type | overall | scored | agent USD | model USD | Exa USD | E2B USD | latency s | turns | tool calls | refused |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| vals-01 | Market Analysis | wrong | yes | $0.0676 | $0.0146 | $0.0530 | $0.0000 | 59.8 | 10 | 17 | 0 |
| vals-02 | Trends | wrong | yes | $0.0203 | $0.0070 | $0.0130 | $0.0003 | 42.8 | 4 | 5 | 0 |
| vals-03 | Beat or Miss | wrong | yes | $0.0094 | $0.0014 | $0.0080 | $0.0000 | 6.4 | 2 | 2 | 0 |
| vals-04 | Complex Retrieval | right | yes | $0.0180 | $0.0019 | $0.0160 | $0.0001 | 10.3 | 4 | 5 | 0 |
| vals-05 | Simple retrieval - Qualitative | right | yes | $0.0276 | $0.0036 | $0.0240 | $0.0000 | 13.1 | 4 | 6 | 0 |
| vals-06 | Complex Retrieval | wrong | yes | $0.0317 | $0.0037 | $0.0280 | $0.0000 | 13.4 | 4 | 7 | 0 |
| vals-07 | Simple retrieval - Qualitative | right | yes | $0.0046 | $0.0006 | $0.0040 | $0.0000 | 3.8 | 2 | 1 | 0 |
| vals-08 | Simple retrieval - Quantitative | wrong | yes | $0.0388 | $0.0055 | $0.0320 | $0.0013 | 53.1 | 8 | 12 | 0 |
| vals-09 | Beat or Miss | right | yes | $0.0189 | $0.0029 | $0.0160 | $0.0000 | 10.1 | 3 | 4 | 0 |
| vals-10 | Numerical Reasoning | right | yes | $0.0094 | $0.0014 | $0.0080 | $0.0001 | 6.2 | 3 | 3 | 0 |
| vals-12 | Financial Modeling  Projections | wrong | no | $0.0158 | $0.0044 | $0.0110 | $0.0005 | 27.8 | 5 | 7 | 0 |
| vals-13 | Numerical Reasoning | right | yes | $0.0325 | $0.0103 | $0.0220 | $0.0001 | 32.9 | 9 | 11 | 0 |
| vals-14 | Trends | wrong | no | $0.0129 | $0.0039 | $0.0090 | $0.0000 | 15.3 | 3 | 3 | 0 |
| vals-15 | Numerical Reasoning | right | yes | $0.0096 | $0.0015 | $0.0080 | $0.0001 | 6.7 | 3 | 3 | 0 |
| vals-16 | Complex Retrieval | wrong | no | $0.0227 | $0.0067 | $0.0160 | $0.0000 | 27.0 | 5 | 7 | 0 |
| vals-17 | Trends | right | yes | $0.0143 | $0.0022 | $0.0120 | $0.0001 | 8.2 | 3 | 4 | 0 |
| vals-18 | Simple retrieval - Qualitative | right | yes | $0.0451 | $0.0101 | $0.0350 | $0.0000 | 44.0 | 7 | 11 | 0 |
| vals-19 | Numerical Reasoning | right | yes | $0.0108 | $0.0018 | $0.0090 | $0.0000 | 10.2 | 4 | 3 | 0 |
| vals-20 | Numerical Reasoning | right | yes | $0.0094 | $0.0014 | $0.0080 | $0.0000 | 3.9 | 2 | 2 | 0 |
| vals-21 | Simple retrieval - Qualitative | right | yes | $0.0568 | $0.0166 | $0.0380 | $0.0022 | 76.9 | 15 | 23 | 0 |
| vals-22 | Numerical Reasoning | wrong | no | $0.0095 | $0.0015 | $0.0080 | $0.0001 | 7.5 | 3 | 3 | 0 |
| vals-23 | Simple retrieval - Qualitative | right | yes | $0.0533 | $0.0108 | $0.0410 | $0.0016 | 64.1 | 9 | 16 | 0 |
| vals-24 | Numerical Reasoning | right | yes | $0.0703 | $0.0103 | $0.0600 | $0.0000 | 38.7 | 9 | 16 | 0 |
| vals-25 | Simple retrieval - Qualitative | wrong | yes | $0.0368 | $0.0131 | $0.0210 | $0.0027 | 93.3 | 12 | 20 | 0 |
| vals-26 | Numerical Reasoning | right | yes | $0.0089 | $0.0009 | $0.0080 | $0.0000 | 4.7 | 2 | 2 | 0 |
| vals-27 | Simple retrieval - Qualitative | right | yes | $0.0514 | $0.0154 | $0.0360 | $0.0000 | 55.3 | 8 | 15 | 0 |
| vals-28 | Simple retrieval - Quantitative | right | yes | $0.0328 | $0.0091 | $0.0230 | $0.0007 | 36.0 | 6 | 9 | 0 |
| vals-29 | Simple retrieval - Qualitative | right | yes | $0.0634 | $0.0204 | $0.0430 | $0.0000 | 87.1 | 12 | 19 | 0 |
| vals-30 | Financial Modeling  Projections | right | yes | $0.0382 | $0.0110 | $0.0270 | $0.0002 | 34.6 | 9 | 13 | 0 |
| vals-31 | Financial Modeling  Projections | right | yes | $0.0101 | $0.0021 | $0.0080 | $0.0001 | 8.7 | 3 | 3 | 0 |
| vals-32 | Simple retrieval - Quantitative | right | yes | $0.0099 | $0.0018 | $0.0080 | $0.0001 | 7.7 | 3 | 3 | 0 |
| vals-33 | Adjustments | wrong | yes | $0.0633 | $0.0149 | $0.0480 | $0.0004 | 54.3 | 13 | 19 | 0 |
| vals-34 | Simple retrieval - Quantitative | right | yes | $0.0092 | $0.0012 | $0.0080 | $0.0000 | 4.5 | 2 | 2 | 0 |
| vals-35 | Adjustments | right | yes | $0.0048 | $0.0008 | $0.0040 | $0.0000 | 5.4 | 2 | 1 | 0 |
| vals-36 | Simple retrieval - Quantitative | right | yes | $0.0092 | $0.0012 | $0.0080 | $0.0000 | 8.1 | 2 | 2 | 0 |
| vals-37 | Simple retrieval - Quantitative | right | yes | $0.0149 | $0.0019 | $0.0130 | $0.0000 | 8.9 | 3 | 4 | 0 |
| vals-38 | Beat or Miss | wrong | yes | $0.0103 | $0.0022 | $0.0080 | $0.0001 | 11.8 | 3 | 3 | 0 |
| vals-39 | Simple retrieval - Qualitative | right | yes | $0.0248 | $0.0068 | $0.0180 | $0.0000 | 19.9 | 4 | 6 | 0 |
| vals-40 | Adjustments | wrong | yes | $0.0223 | $0.0073 | $0.0150 | $0.0000 | 20.9 | 4 | 6 | 0 |
| vals-41 | Simple retrieval - Quantitative | right | yes | $0.0094 | $0.0014 | $0.0080 | $0.0000 | 7.8 | 2 | 2 | 0 |
| vals-42 | Market Analysis | wrong | yes | $0.0647 | $0.0120 | $0.0520 | $0.0008 | 44.5 | 6 | 14 | 0 |
| vals-43 | Financial Modeling  Projections | wrong | no | $0.0342 | $0.0115 | $0.0220 | $0.0007 | 67.9 | 7 | 9 | 0 |
| vals-44 | Simple retrieval - Quantitative | right | yes | $0.0258 | $0.0061 | $0.0190 | $0.0007 | 34.2 | 5 | 8 | 0 |
| vals-45 | Adjustments | right | yes | $0.0096 | $0.0016 | $0.0080 | $0.0000 | 5.8 | 2 | 2 | 0 |
| vals-46 | Market Analysis | wrong | yes | $0.0657 | $0.0168 | $0.0480 | $0.0009 | 80.5 | 10 | 16 | 0 |
| vals-47 | Beat or Miss | right | yes | $0.0142 | $0.0021 | $0.0120 | $0.0001 | 17.5 | 4 | 5 | 0 |
| vals-48 | Beat or Miss | wrong | yes | $0.0148 | $0.0028 | $0.0120 | $0.0000 | 11.8 | 3 | 3 | 0 |
| vals-49 | Beat or Miss | wrong | yes | $0.0419 | $0.0089 | $0.0330 | $0.0000 | 38.2 | 6 | 9 | 0 |
