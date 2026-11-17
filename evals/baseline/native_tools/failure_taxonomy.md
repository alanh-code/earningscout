# Failure taxonomy: native-tools baseline

The per-question labels below were derived from an earlier `runs/first-run` (unrestricted tools, before the protocol as-of date was fixed). Wrong answers in that run: 21 (from `results.csv`, exclusions removed). Labeled: 21.

The current `runs/first-run` (protocol as-of Thursday, May 1, 2025) still has 21 wrong answers after exclusions. Versus the labeled set, vals-10 and vals-40 are now right, and vals-31 and vals-35 are newly wrong and are not labeled here.

Excluded from scoring and counts: vals-11, vals-50 (answer depends on an unstated relative time period).

Evidence comes from the original answer, the judge's failed checks, and one replay per question with the same setup (the original run saved no tool traces). Replays are a separate sample, so they show search behavior, not the exact original path.

## Categories

| Category | Definition | Primary | Secondary |
|---|---|---:|---:|
| `shallow_retrieval` | A required item was never retrieved: the agent stopped at search snippets or one secondary page and did not open the filing section that holds it. | 4 | 0 |
| `omitted_item` | The needed figure or point was in the retrieved material (or computable from it) but was left out of the answer. | 4 | 2 |
| `interpretation_choice` | The question is open to more than one reading; the agent picked a different, stated definition, assumption, or scope than the gold (cash-flow basis, tax treatment, peer set, risk scope). | 4 | 1 |
| `guidance_benchmark` | Beat/miss measured against a different guidance reference than the gold (low end vs midpoint, margin range vs dollar guide, final vs initial range). | 3 | 0 |
| `later_data` | Used data newer than the time frame the question implies (post-close status, later raised guidance, latest releases), so time-bound gold points are missed. | 2 | 1 |
| `unsourced_figure` | A precise number came from memory or rounded inputs rather than the filing, so it is close but not exact. | 1 | 2 |
| `misread_source` | Reached a source with the answer but misread or misdescribed a figure or item. | 2 | 0 |
| `gold_issue` | The model answer is defensible and the gold is the problem (inputs rounded differently, narrower than the question, or ambiguous). | 1 | 5 |

Two-pass agreement on primary cause (hand first pass vs independent model pass): 17/21 (81%). Disagreements were re-read against the trace and settled by hand; see the resolution column.

## Per question

| id | type | primary | secondary | evidence | second pass | resolution |
|---|---|---|---|---|---|---|
| vals-01 | Market Analysis | `later_data` | `omitted_item` | Searched 'merger completed national security agreement'; answered June 2025 post-close status (NSA, Granite City) instead of the Dec 2023 announcement framing; missed date, 100k jobs, $14B pledge, $4B mill. | later_data |  |
| vals-02 | Trends | `omitted_item` |  | All six ARM values match the 10-Ks; computed +8% total but never stated the ~2.8%/yr 2019-22 rate, and attributed flatness to low-price regions, not ad plans. | omitted_item |  |
| vals-06 | Complex Retrieval | `later_data` |  | Searched 'Amazon 2025 capex guidance'; used Oct 2025 raised ~$125B (and GOOG $91-93B) instead of Feb 2025 guide AMZN $105.2B. Replay identical. | later_data |  |
| vals-08 | Simple retrieval - Quantitative | `interpretation_choice` | `gold_issue` | TKO 10-Q (sec.gov R8.htm) says '$3.25 billion plus a $50 million purchase price adjustment'; model added them to $3.3B ('I added the two figures myself'); gold keeps $3.25B. Replay identical. | interpretation_choice |  |
| vals-10 | Numerical Reasoning | `unsourced_figure` |  | Zero tool calls; 2022 revenue $1,906.2M 'from memory' vs 10-K $1,905.871M (CAGR 22.6% still right). | unsourced_figure |  |
| vals-12 | Financial Modeling  Projections | `guidance_benchmark` | `gold_issue` | Inputs match gold (avg +4.54%, Q1 NT$825.1B); compared to low end and called it a beat, gold measures vs midpoint (-1.2% miss). Model used TSMC's stated 32.8 FX; gold uses 32.88. Replay identical. | guidance_benchmark |  |
| vals-14 | Trends | `misread_source` | `interpretation_choice` | Used 10-K total CFO $4,504M for FY2022 (incl. Zillow Offers wind-down) giving ~224%; gold 24.8% implies CFO ~$601M (ex-Offers). Model flagged the distortion but kept it. Replay identical. | misread_source | Adopted second pass: total CFO $4,504M (incl. discontinued Zillow Offers) was divided by continuing-ops revenue $1,958M, a mixed basis rather than a defensible choice. |
| vals-16 | Complex Retrieval | `shallow_retrieval` | `gold_issue` | Only fetch was the nasdaq.com pricing release; never opened the certificate of designations, so 'no optional redemption' is missing. Common-dividend block stated as conditional (as filings word it), judged a contradiction. | shallow_retrieval |  |
| vals-22 | Numerical Reasoning | `gold_issue` |  | GBV from 10-Ks ($63,212/$73,252/$81,784M) divided by letter nights 393.7/448.2/491.5M; gold divides by 10-K nights rounded to 394/448/492M (63,212/394=160.44, 81,784/492=166.23). Replay identical. | gold_issue |  |
| vals-25 | Simple retrieval - Qualitative | `interpretation_choice` | `omitted_item` | Fetched the FY2024 10-K and summarized the 'Legal and Regulatory' section (privacy laws, money transmitter, AI, tax); gold also counts cybersecurity, third-party breach and trust risks as regulatory. | omitted_item | Kept first pass: the cyber section was in the fetched 10-K (second pass is right that it was available), but it was left out because the model scoped 'regulatory' to the Legal and Regulatory heading; omitted_item moved to secondary. |
| vals-27 | Simple retrieval - Qualitative | `shallow_retrieval` |  | Read 10-K search snippets only (no fetch); snippet ends before the redemption paragraph, model said 'the 10-K text I retrieved did not include the redemption terms', so the pre-2037 make-whole term is missing. | shallow_retrieval |  |
| vals-33 | Adjustments | `interpretation_choice` |  | Boeing 10-K inputs: debt $53,864M x 3% = $1,616M, assumed no tax shield (13.7%); gold $1.261B/10.7% implies after-tax at ~21%. Model's own 21% alternative ($1.28B/10.8%) is close but on a different debt base. | interpretation_choice |  |
| vals-36 | Simple retrieval - Quantitative | `shallow_retrieval` | `gold_issue` | One search; snippets gave $12.50, $1.75B and $2.4B (Redfin 425 FAQ); exchange ratio 0.7926 never retrieved. Question's parenthetical did not ask for the ratio. | shallow_retrieval |  |
| vals-38 | Beat or Miss | `guidance_benchmark` |  | Midpoint taken from the 2.3-2.4% margin range (2.35%) -> 29 bps; gold builds it from dollar guidance $102.5M / $4.315B GB (2.375%) -> 26.1 bps, which the model gave only as an alternative. | guidance_benchmark |  |
| vals-39 | Simple retrieval - Qualitative | `omitted_item` | `later_data` | Answer says full-year EPS was cut 'to $5.10-$5.60 from $6.50-$7.50', so the Jan 2025 guide was seen, and a retrieved snippet says that guide 'represents growth of 20% year-over-year'; the answer framed full-year EPS only as a level, not YoY growth. Also leaned on 2025-2026 releases. | omitted_item | Adopted second pass: the growth framing was in retrieved material, so the omission is the root cause; later releases kept as secondary. |
| vals-40 | Adjustments | `misread_source` |  | Said the lodging/withholding/transactional tax adjustment 'no longer appear[s] in the latest letters'; replay of the same search found it in the Q3 2024 and Q1 2026 10-Q reconciliations ('Lodging taxes, host withholding taxes, and transactional taxes, net'). | misread_source |  |
| vals-42 | Market Analysis | `interpretation_choice` | `unsourced_figure` | Chose beverage peers (COKE, MNST, CCEP in replay) instead of gold's KHC and SJM; PEP 77% used an assumed $5.33 DPS (gold 0.75). KDP 83% and KO 79% match. | interpretation_choice |  |
| vals-43 | Financial Modeling  Projections | `omitted_item` | `unsourced_figure` | One search (Q4 2024 release); revenue 'from my recollection', take rates only ~27.0% (gold 27.04/27.02%); segment growth (Mobility 25%, Delivery 17%, Freight 2%) omitted. | unsourced_figure | Kept first pass: 3 of 5 failed checks are the omitted segment growth rates (in retrieved release text per second pass); the ~27.0% take-rate precision from remembered revenue is secondary. |
| vals-46 | Market Analysis | `shallow_retrieval` | `gold_issue` | One fetch (Q3 2024 exhibit 99.3); Spruce price 'I didn't retrieve' (gold $19M). Said Residential grew 12% in Q3 2024 (true in that release); gold claims a decline. | shallow_retrieval |  |
| vals-48 | Beat or Miss | `omitted_item` |  | Fetched the Q3 2024 letter whose guidance table lists SBC $64M, capex $10M, shares 71M; answer covered only IFP, GEP, revenue and Adj. EBITDA. | omitted_item |  |
| vals-49 | Beat or Miss | `guidance_benchmark` |  | Compared FY2024 +6% to the narrowed final range (+4-5%) and called it a beat; gold uses the initial +4-6% range ('met'). Model noted it matched the top of the initial range. Replay identical. | guidance_benchmark |  |

## Insights

1. Retrieval depth is the largest fixable gap. In 8 of 21 (shallow_retrieval 4, omitted_item 4) the needed item was either never opened or seen and dropped. The agent mostly runs web_search inside code and reads result snippets; 17 of 23 replays never called web_fetch. A rule like "open the primary filing section before answering" plus a rubric-style completeness check before the final answer targets both.
2. Beat/miss and modeling questions fail on the reference, not the arithmetic. In 7 of 21 (guidance_benchmark 3, interpretation_choice 4) the retrieved inputs largely matched the gold but the benchmark, assumption, or scope differed (low end vs midpoint, margin range vs dollar guide, final vs initial range, tax shield, peer set). No pure calculation errors were found. Defaulting to the midpoint of the original dollar guidance and stating one headline assumption would fix most.
3. Some misses are gold or time-frame artifacts. vals-22 is a gold rounding artifact (10-K whole-million nights), and 2 more (vals-01, vals-06) answer for a later date than the question implies; 6 more carry a gold_issue or later_data secondary. These should go to the grading audit before being counted as model failures.

## Caveat

The vals-27 replay surfaced the public benchmark file (github.com/vals-ai/finance-agent, data/public.csv) in web_search results and used it for the 2057 scheduled maturity. Web search can leak gold answers; a domain block for that repo is worth adding to the agent run.
