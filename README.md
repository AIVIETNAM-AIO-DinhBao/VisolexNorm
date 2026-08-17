# ViSoLexNorm

Vietnamese social-media lexical normalization with BARTpho. The project uses
ViLexNorm as gold data and ViSoLex as an unlabeled corpus for weak-labeling.

## Phase 1: prepare data

Place raw files under `data/raw/` (this directory is ignored by Git), then run
the scripts below with the field names used by the raw datasets.

```bash
python scripts/prepare_vilexnorm.py --train data/raw/vilexnorm/train.jsonl --dev data/raw/vilexnorm/dev.jsonl --test data/raw/vilexnorm/test.jsonl --input-field original --target-field normalized
```

```bash
python scripts/prepare_visolex.py --source ViHSD data/raw/visolex/vihsd.csv text --source UIT-VSMEC data/raw/visolex/vsmec.csv text --source ViHOS data/raw/visolex/vihos.csv text --source ViSpamReviews data/raw/visolex/spam_reviews.csv text --source UIT-ViSFD data/raw/visolex/visfd.csv text
```

```bash
python scripts/check_data.py
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
python scripts/prepare_vilexnorm.py --train data/raw/vilexnorm/train.csv --dev data/raw/vilexnorm/dev.csv --test data/raw/vilexnorm/test.csv --input-field original --target-field normalized
python scripts/prepare_visolex.py --source ViHSD data/raw/visolex/ViHSD.csv free_text --source UIT-VSMEC data/raw/visolex/UIT-VSMEC.csv Sentence --source ViHOS data/raw/visolex/ViHOS.csv sentence --source ViSpamReviews data/raw/visolex/ViSpamReviews.csv Comment --source UIT-ViSFD data/raw/visolex/UIT-ViSFD.csv comment
python scripts/check_data.py
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