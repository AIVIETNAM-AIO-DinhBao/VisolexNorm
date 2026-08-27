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

try:
    from scripts._bootstrap import ensure_project_root
except ModuleNotFoundError:
    from _bootstrap import ensure_project_root

ensure_project_root()

from visolexnorm.common.io import clean_text, read_jsonl, read_rows, write_jsonl
from visolexnorm.common.progress import log_event


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
    parser.add_argument("--log-every", type=int, default=5000, help="Emit progress every N raw rows per source")
    parser.add_argument("--quiet", action="store_true", help="Suppress operational progress logs")
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
        source_rows = read_rows(path)
        log_event("START", f"ViSoLex preprocessing: source={name} raw_rows={len(source_rows)} input={path}", quiet=args.quiet)
        for position, row in enumerate(source_rows, start=1):
            raw_counts[name] += 1
            text = clean_text(row.get(text_field))
            if text is None:
                empty_counts[name] += 1
            elif text in protected_texts:
                overlap_counts[name] += 1
            elif text in seen:
                duplicate_counts[name] += 1
            else:
                seen.add(text)
                records.append(
                    {
                        "id": f"visolex_{len(records) + 1:06d}",
                        "dataset": "ViSoLex",
                        "original_source": name,
                        "input_text": text,
                    }
                )
            if args.log_every > 0 and position % args.log_every == 0:
                log_event("PROGRESS", f"ViSoLex preprocessing: source={name} raw={position}/{len(source_rows)} kept_total={len(records)}", quiet=args.quiet)
        log_event("DONE", f"ViSoLex preprocessing: source={name} raw={raw_counts[name]} kept={sum(record['original_source'] == name for record in records)} empty={empty_counts[name]} duplicates={duplicate_counts[name]} protected_overlap={overlap_counts[name]}", quiet=args.quiet)

    output = args.output_dir / "visolex_unlabeled.jsonl"
    write_jsonl(records, output)
    log_event("DONE", f"ViSoLex preprocessing: total={len(records)} output={output}", quiet=args.quiet)


if __name__ == "__main__":
    main()
