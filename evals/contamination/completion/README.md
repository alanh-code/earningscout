# Completion test

The model gets the first part of a question and is asked for the rest. A model that reproduces the hidden part of a Vals question far better than it does for a question that never existed has likely seen the Vals question in training.

## Inputs

* All 50 questions in `data/vals/public.csv`.
* `../controls.csv`: 50 new questions in the same style about real filings, written for this test. They cannot be in any training data, so they show how guessable a question ending is on its own. Same columns as the Vals file; ids `ctrl-01`… follow row order.

## Method

1. Keep the first 60% or so of each question, cut at a word boundary, so the hidden part still holds specific details such as company, year and metric.
2. Ask each question two ways, in the closed environment:
   * **guided:** names the source, the Vals AI Finance Agent benchmark public set, and asks for the continuation as close to the original wording as the model can, saying a guess is fine
   * **general:** asks only to complete the question, saying a guess is fine
3. Score each answer against the real ending, as described below.

## Scoring

`score()` compares the model's ending with the real ending by embedding cosine similarity. Both endings are encoded with a [Sentence Transformers](https://www.sbert.net) model, `all-mpnet-base-v2`, run locally, and the score is the cosine of the two vectors: 1 for the same meaning, about 0 for unrelated text.

Vals and control endings are scored the same way, with the same model and settings. The model name and library version are recorded with each run, since scores from different models are not comparable.

The score measures closeness of meaning. It changes little when only a value changes: on a test ending, replacing "Q4 2024" with "Q1 2026" still scored 0.96. Read a high score as "same kind of ending", and check the specific names, periods and figures in `results.csv` before counting it as recall.

## Running it

```bash
.venv/bin/python evals/contamination/completion/run_completion.py --dry-run
.venv/bin/python evals/contamination/completion/run_completion.py --name official
```

`--dry-run` prints where each question is cut and calls nothing. `--ids vals-07,ctrl-01` runs only those questions. `--vals-only` skips the controls. The full run sends 200 requests. The saved run used `--cut 0.4`.

Each call sends only `model`, `max_tokens`, one user message and `thinking: {"type": "between_tools"}`, which turns thinking off so the answer is recall alone. The client gets the key from `.env` and the API URL explicitly, so nothing in the surrounding shell changes where requests go. The script stops at the first response that has a non text block, a stop reason other than `end_turn`, any server tool use, or a different model.

Each run writes to `runs/<name>/` (pass `--name`): `raw/` holds every request and full response, `results.csv` the scores per question and mode, and `summary.md` the averages by group and mode with the highest scoring Vals questions. `runs/official/analysis.md` adds the Vals-versus-control statistical comparison.

## Reading the results

Vals well above control, and guided above general, suggests memorization. A low score does not prove the model never saw a question: it may know the content without reproducing it word for word.
