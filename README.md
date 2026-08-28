# ViSoLexNorm

Vietnamese social-media lexical normalization with BARTpho. The project uses
ViLexNorm as gold data and ViSoLex as an unlabeled corpus for weak-labeling.

## Phase 1: prepare data

Place raw files under `data/raw/` (this directory is ignored by Git), then run
the scripts below with the field names used by the raw datasets.

```bash
python scripts/data.py prepare-vilexnorm --train data/raw/vilexnorm/train.jsonl --dev data/raw/vilexnorm/dev.jsonl --test data/raw/vilexnorm/test.jsonl --input-field original --target-field normalized
```

```bash
python scripts/data.py prepare-visolex --source ViHSD data/raw/visolex/vihsd.csv text --source UIT-VSMEC data/raw/visolex/vsmec.csv text --source ViHOS data/raw/visolex/vihos.csv text --source ViSpamReviews data/raw/visolex/spam_reviews.csv text --source UIT-ViSFD data/raw/visolex/visfd.csv text
```

```bash
python scripts/data.py validate
```

## Current downloaded data

Raw data is arranged as follows:

```text
data/raw/vilexnorm/{train,dev,test}.csv
data/raw/visolex/{ViHSD,UIT-VSMEC,ViHOS,ViSpamReviews,UIT-ViSFD}.csv
```

The verified field mapping is:

| Dataset | Text field |
| --- | --- |
| ViLexNorm | `original` → `normalized` |
| ViHSD | `free_text` |
| UIT-VSMEC | `Sentence` |
| ViHOS | `sentence` |
| ViSpamReviews | `Comment` |
| UIT-ViSFD | `comment` |

The exact commands used for the current artifacts are:

```bash
python scripts/data.py prepare-vilexnorm --train data/raw/vilexnorm/train.csv --dev data/raw/vilexnorm/dev.csv --test data/raw/vilexnorm/test.csv --input-field original --target-field normalized
python scripts/data.py prepare-visolex --source ViHSD data/raw/visolex/ViHSD.csv free_text --source UIT-VSMEC data/raw/visolex/UIT-VSMEC.csv Sentence --source ViHOS data/raw/visolex/ViHOS.csv sentence --source ViSpamReviews data/raw/visolex/ViSpamReviews.csv Comment --source UIT-ViSFD data/raw/visolex/UIT-ViSFD.csv comment
python scripts/data.py validate
```

Current Phase 1 counts:

| Artifact/source | Records kept |
| --- | ---: |
| ViLexNorm Train | 8,372 |
| ViLexNorm Dev | 1,050 |
| ViLexNorm Test | 1,045 |
| ViSoLex / ViHSD | 30,579 |
| ViSoLex / UIT-VSMEC | 6,916 |
| ViSoLex / ViHOS | 0 |
| ViSoLex / ViSpamReviews | 19,805 |
| ViSoLex / UIT-ViSFD | 11,111 |
| **ViSoLex total** | **68,411** |

`ViHOS` is entirely duplicated by the earlier `ViHSD` source in this public
release, so global exact deduplication retains the ViHSD provenance and reports
zero kept ViHOS records. The raw ViHOS CSV remains in `data/raw/visolex/` for
audit.

Supported raw formats are CSV, TSV, JSON, and JSONL; raw files must be UTF-8
(UTF-8 with BOM is also accepted). The scripts only remove empty records,
normalize Unicode/whitespace, deduplicate ViSoLex exact inputs across the
combined corpus, and remove ViSoLex sentences that exactly overlap ViLexNorm
Dev/Test. The first configured source is retained for cross-source duplicates;
the raw files remain available for audit. The scripts do not normalize
teencode, spelling, case, punctuation, or Vietnamese diacritics.

## Phase 2: Model A on Kaggle

Upload the repository code (or clone this GitHub repository) and the two
processed gold files to private Kaggle Datasets. Attach both datasets to a GPU
notebook, set `CODE_DIR` and `DATA_DIR` in
`notebooks/train_model_a_kaggle.ipynb`, then run all cells. The notebook runs
only Train/Dev and exports the checkpoint plus Dev artifacts to
`/kaggle/working`.

## Phase 3: candidates on Kaggle, Gemini review on local

### 1. Generate candidates on Kaggle T4

Attach private Kaggle datasets containing `visolex_unlabeled.jsonl` and the
exported `checkpoints/model_a/` directory. Enable a **T4 GPU**, then run
`notebooks/generate_visolex_candidates_kaggle.ipynb`. It creates:

```text
data/intermediate/visolex_model_a_candidates.jsonl
```

Download the resulting artifact to the local laptop. Do **not** put Gemini API
keys in Kaggle; Gemini is used only for local, offline data preparation.

### 2. Review locally with Gemini round-robin keys

Create `.env` from `.env.example`; it is ignored by Git. Add comma-separated
keys and choose a model you can access:

```dotenv
GEMINI_API_KEYS=key_1,key_2,key_3
GEMINI_MODEL=gemini-2.5-flash
```

Install the local reviewer dependencies:

```bash
pip install -r requirements.txt
```

Select the reproducible source/confidence-stratified review set (strict budget:
20,000; pilot: 240 in `configs/llm_review_config.json`):

```bash
python scripts/candidates.py select-review --candidates data/intermediate/visolex_model_a_candidates.jsonl --config configs/llm_review_config.json
```

First run the 240-example pilot and manually inspect every result. The
reviewer uses `KEEP` / `EDIT` / `REJECT`, saves each successful result by ID,
round-robins the configured API keys for requests/retries, and logs failures
without exposing keys:

```bash
python scripts/review_candidates.py --mode pilot --config configs/llm_review_config.json
```

### Operational progress and resume

Long-running scripts emit flushed, durable terminal lines rather than an
interactive progress bar, so progress remains visible in PowerShell, Kaggle,
and saved logs:

```text
[START] Gemini review: total=240 cached=0 pending=240 batches=16 ...
[REQUEST] Gemini batch 1/16: samples=15 attempt=1/5
[PROGRESS] Gemini review: 15/240 (6.2%) elapsed=0:08 eta=2:02 ...
[RETRY] Gemini batch 4/16: ... category=quota ... wait=4.2s ...
[DONE] Gemini pilot review completed: 240 IDs committed in cache=...
```

`[RESUME]` means already committed IDs were recovered from SQLite and are not
charged again. `Ctrl+C` is safe between requests: rerun the same command to
continue. `[WARNING]` identifies an exhausted batch; the terminal never prints
API keys, prompts, raw API responses, or sample text. Pass `--quiet` only for
CI/noninteractive runs.

After audit, freeze the prompt using a report bound to the current prompt hash and
all 240 pilot IDs; then run the full manifest. SQLite automatically resumes the
frozen-v1 namespace:

```bash
python scripts/freeze_review_prompt.py --pilot-report outputs/pilot_review_report.json --approved
python scripts/review_candidates.py --mode full --config configs/llm_review_config.json
```

Build final weak labels and statistics locally:

```bash
python scripts/data.py export-protected-hashes
python scripts/build_weak_labels.py --protected-hashes data/processed/vilexnorm_protected_input_hashes.txt --model gemini-2.5-flash
python scripts/audit_weak_labels.py --weak-labels data/processed/visolex_weak_labeled.jsonl --stats outputs/weak_label_stats.json
```

This produces `data/processed/visolex_weak_labeled.jsonl` and
`outputs/weak_label_stats.json`. Upload only these finalized artifacts (plus
the recorded configs) to a private Kaggle Dataset for Phase 4. Every weak label
used by Model B has a Gemini review decision and retains its ViSoLex/Model A
provenance.