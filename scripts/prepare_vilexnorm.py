"""Convert the existing ViLexNorm Train/Dev/Test files to the project JSONL schema.

Example:
python scripts/prepare_vilexnorm.py \
  --train data/raw/vilexnorm/train.jsonl \
  --dev data/raw/vilexnorm/dev.jsonl \
  --test data/raw/vilexnorm/test.jsonl \
  --input-field original --target-field normalized
"""

from __future__ import annotations

import argparse
from pathlib import Path

from data_utils import clean_text, read_rows, write_jsonl


def process_split(
    raw_path: Path, split: str, input_field: str, target_field: str
) -> tuple[list[dict[str, str]], int]:
    rows = read_rows(raw_path)
    records: list[dict[str, str]] = []
    skipped = 0

    for row in rows:
        source = clean_text(row.get(input_field))
        target = clean_text(row.get(target_field))
        if source is None or target is None:
            skipped += 1
            continue
        records.append(
            {
                "id": f"vilexnorm_{split}_{len(records) + 1:06d}",
                "dataset": "ViLexNorm",
                "split": split,
                "input_text": source,
                "target_text": target,
                "label_source": "human",
            }
        )
    return records, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare ViLexNorm processed JSONL files.")
    parser.add_argument("--train", type=Path, required=True, help="Raw ViLexNorm train file")
    parser.add_argument("--dev", type=Path, required=True, help="Raw ViLexNorm dev file")
    parser.add_argument("--test", type=Path, required=True, help="Raw ViLexNorm test file")
    parser.add_argument("--input-field", required=True, help="Raw field containing noisy input")
    parser.add_argument("--target-field", required=True, help="Raw field containing human target")
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    args = parser.parse_args()

    for split, raw_path in (("train", args.train), ("dev", args.dev), ("test", args.test)):
        if not raw_path.is_file():
            parser.error(f"Raw {split} file does not exist: {raw_path}")
        records, skipped = process_split(raw_path, split, args.input_field, args.target_field)
        output = args.output_dir / f"vilexnorm_{split}.jsonl"
        write_jsonl(records, output)
        print(f"{split}: raw={len(records) + skipped}, kept={len(records)}, skipped_empty={skipped} -> {output}")


if __name__ == "__main__":
    main()
