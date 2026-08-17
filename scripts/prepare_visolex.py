"""Build the unlabeled ViSoLex corpus from its five original sources.

Repeat --source once per source using: SOURCE_NAME RAW_FILE TEXT_FIELD
Example:
python scripts/prepare_visolex.py \
  --source ViHSD data/raw/visolex/vihsd.csv free_text \
  --source UIT-VSMEC data/raw/visolex/vsmec.json sentence \
  --source ViHOS data/raw/visolex/vihos.jsonl text \
  --source ViSpamReviews data/raw/visolex/spam_reviews.csv review \
  --source UIT-ViSFD data/raw/visolex/visfd.csv comment
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from data_utils import clean_text, read_jsonl, read_rows, write_jsonl


ALLOWED_SOURCES = {"ViHSD", "UIT-VSMEC", "ViHOS", "ViSpamReviews", "UIT-ViSFD"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare ViSoLex unlabeled JSONL.")
    parser.add_argument(
        "--source",
        action="append",
        nargs=3,
        metavar=("NAME", "RAW_FILE", "TEXT_FIELD"),
        required=True,
        help="Repeat for each source: NAME RAW_FILE TEXT_FIELD",
    )
    parser.add_argument(
        "--vilexnorm-dir",
        type=Path,
        default=Path("data/processed"),
        help="Folder containing vilexnorm_dev.jsonl and vilexnorm_test.jsonl",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    args = parser.parse_args()

    names = [source[0] for source in args.source]
    invalid_names = set(names) - ALLOWED_SOURCES
    if invalid_names:
        parser.error(f"Unknown source name(s): {sorted(invalid_names)}")
    if len(set(names)) != len(names):
        parser.error("Each source may be supplied only once.")

    dev_path = args.vilexnorm_dir / "vilexnorm_dev.jsonl"
    test_path = args.vilexnorm_dir / "vilexnorm_test.jsonl"
    if not dev_path.is_file() or not test_path.is_file():
        parser.error("Prepare ViLexNorm dev/test first; both files are required for leakage removal.")
    protected_texts = {
        record["input_text"]
        for path in (dev_path, test_path)
        for record in read_jsonl(path)
        if isinstance(record.get("input_text"), str)
    }

    # Deduplicate the final training corpus globally. The first configured
    # source is retained as provenance when the same text exists in two sets.
    seen: set[str] = set()
    records: list[dict[str, str]] = []
    raw_counts: Counter[str] = Counter()
    empty_counts: Counter[str] = Counter()
    duplicate_counts: Counter[str] = Counter()
    overlap_counts: Counter[str] = Counter()

    for name, raw_file, text_field in args.source:
        path = Path(raw_file)
        if not path.is_file():
            parser.error(f"Raw file for {name} does not exist: {path}")
        for row in read_rows(path):
            raw_counts[name] += 1
            text = clean_text(row.get(text_field))
            if text is None:
                empty_counts[name] += 1
                continue
            if text in protected_texts:
                overlap_counts[name] += 1
                continue
            if text in seen:
                duplicate_counts[name] += 1
                continue
            seen.add(text)
            records.append(
                {
                    "id": f"visolex_{len(records) + 1:06d}",
                    "dataset": "ViSoLex",
                    "original_source": name,
                    "input_text": text,
                }
            )

    output = args.output_dir / "visolex_unlabeled.jsonl"
    write_jsonl(records, output)
    print(f"Wrote {len(records)} records -> {output}")
    for name in names:
        final = sum(record["original_source"] == name for record in records)
        print(
            f"{name}: raw={raw_counts[name]}, kept={final}, empty={empty_counts[name]}, "
            f"duplicates={duplicate_counts[name]}, dev_test_overlap={overlap_counts[name]}"
        )


if __name__ == "__main__":
    main()
