# Fifty-control completion probe

Model: claude-sonnet-5-5; 40% prefix; 200 fresh requests; all existing closed-environment checks passed.

| Set | Prompt | n | Mean | Median | Sample SD | Max | P95 |
|---|---|---:|---:|---:|---:|---:|---:|
| vals | guided | 50 | 0.5072 | 0.5010 | 0.1559 | 0.811 | 0.7733 |
| vals | general | 50 | 0.4446 | 0.4160 | 0.1724 | 0.819 | 0.7714 |
| control | guided | 50 | 0.5305 | 0.5490 | 0.1633 | 0.872 | 0.7940 |
| control | general | 50 | 0.5363 | 0.5565 | 0.1666 | 0.859 | 0.7790 |

## Public versus control
Two-sided asymptotic Mann-Whitney with continuity/tie correction; unadjusted exploratory p-values. Cliff delta positive means public scores higher.
- guided: mean difference=-0.0233; U=1135.0; p=0.429899; Cliff delta=-0.0920.
- general: mean difference=-0.0917; U=821.0; p=0.003136; Cliff delta=-0.3432.

## Control maxima
- ctrl-47 / guided: 0.872
  - Original: If Netflix repeated its 2024 operating cash generation but increased additions to content assets by 8%, what would projected free cash flow be, with every other cash flow item unchanged?
  - Hidden ending: content assets by 8%, what would projected free cash flow be, with every other cash flow item unchanged?
  - Completion: content assets by 10% over the amount it reported in 2024, what would its approximate free cash flow be, assuming all other cash flow items remained unchanged?
- ctrl-47 / general: 0.859
  - Original: If Netflix repeated its 2024 operating cash generation but increased additions to content assets by 8%, what would projected free cash flow be, with every other cash flow item unchanged?
  - Hidden ending: content assets by 8%, what would projected free cash flow be, with every other cash flow item unchanged?
  - Completion: content assets by $2 billion while keeping all other cash flow items unchanged, what would its free cash flow have been?

## Protocol
- Guided uses the same source-neutral wording for both sets; no claim of Vals provenance. General unchanged. Both public prompts were rerun, so no old scores are reused.
- Guided text: This is the beginning of a financial research question. Write how you think that question continues, as close to its original wording as you can. A guess is fine: it will be compared with the real question to measure recall. Reply with only the rest of the question, starting right after the given text.
- Harness unchanged; in-memory input adapter assigns ctrl-01..ctrl-50 by CSV row. Scorer: all-mpnet-base-v2, sentence-transformers 6.2.0.
- Controls have public.csv columns and matching type counts: Market Analysis 3; Trends 3; Beat or Miss 7; Complex Retrieval 3; qualitative retrieval 9; quantitative retrieval 9; Numerical Reasoning 8; Financial Modeling  Projections 4; Adjustments 4.
- Length matching is approximate: public mean/median 22.4/18 words (range 9–69); controls 25.94/23.5 (16–43). Length/predictability remains a confound.
- All 2,500 control/public pairs and 1,225 distinct control/control pairs checked before inference: maximum cosine .715402 and .700107, respectively.
- First 10 controls retained; 40 freshly AI-authored. Ten grouped distinctive-phrase searches covered new controls; returned results showed related financial material, not obvious question copies. No internet-wide absence or training-exclusion guarantee. Earlier ten controls were phrase-checked in the preceding run.
- These are AI-authored completion controls, not verified gold-answer QA items; blank answers/rubrics. Prior public-only results informed the study design.
- All scores rounded to .001 by harness; medians use both middle observations and P95 uses linear interpolation.
- Estimated cost: $0.13212 (17,840 input; 9,644 output tokens at harness $2/$10 per million); not a verified invoice.

Interpretation: public endings scored no higher than fresh controls under either prompt; this does not establish or rule out benchmark contamination.
