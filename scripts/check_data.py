"""Quick validation for the four Phase 1 processed JSONL artifacts."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from data_utils import clean_text, read_jsonl
from phase3_utils import log_event


ALLOWED_SOURCES = {"ViHSD", "UIT-VSMEC", "ViHOS", "ViSpamReviews", "UIT-ViSFD"}


def fail(message: str) -> None:
    raise ValueError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Phase 1 processed data.")
    parser.add_argument("--data-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--samples", type=int, default=3, help="Samples to print per file")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--quiet", action="store_true", help="Suppress operational validation logs")
    args = parser.parse_args()

    all_ids: set[str] = set()
    splits: dict[str, list[dict[str, str]]] = {}
    log_event("START", f"Phase 1 validation: data_dir={args.data_dir}", quiet=args.quiet)
    for split in ("train", "dev", "test"):
        path = args.data_dir / f"vilexnorm_{split}.jsonl"
        if not path.is_file():
            fail(f"Missing file: {path}")
        records = read_jsonl(path)
        for record in records:
            required = {"id", "dataset", "split", "input_text", "target_text", "label_source"}
            if not required <= record.keys():
                fail(f"{path}: missing required field in {record}")
            if record["dataset"] != "ViLexNorm" or record["split"] != split or record["label_source"] != "human":
                fail(f"{path}: invalid constants in {record}")
            if clean_text(record["input_text"]) != record["input_text"] or clean_text(record["target_text"]) != record["target_text"]:
                fail(f"{path}: text is empty or not whitespace-normalized")
            if record["id"] in all_ids:
                fail(f"Duplicate id: {record['id']}")
            all_ids.add(record["id"])
        splits[split] = records
        log_event("PROGRESS", f"Phase 1 validation: split={split} records={len(records)}", quiet=args.quiet)

    visolex_path = args.data_dir / "visolex_unlabeled.jsonl"
    if not visolex_path.is_file():
        fail(f"Missing file: {visolex_path}")
    visolex = read_jsonl(visolex_path)
    inputs: set[str] = set()
    source_counts = {source: 0 for source in sorted(ALLOWED_SOURCES)}
    for record in visolex:
        required = {"id", "dataset", "original_source", "input_text"}
        if not required <= record.keys():
            fail(f"{visolex_path}: missing required field in {record}")
        if record["dataset"] != "ViSoLex" or record["original_source"] not in ALLOWED_SOURCES:
            fail(f"{visolex_path}: invalid dataset/source in {record}")
        text = record["input_text"]
        if clean_text(text) != text:
            fail(f"{visolex_path}: text is empty or not whitespace-normalized")
        if text in inputs:
            fail(f"{visolex_path}: duplicate input_text: {text!r}")
        if record["id"] in all_ids:
            fail(f"Duplicate id: {record['id']}")
        inputs.add(text)
        all_ids.add(record["id"])
        source_counts[record["original_source"]] += 1

    protected = {record["input_text"] for split in ("dev", "test") for record in splits[split]}
    overlaps = inputs & protected
    if overlaps:
        fail(f"ViSoLex still overlaps ViLexNorm Dev/Test ({len(overlaps)} exact input matches).")
    log_event("PROGRESS", f"Phase 1 validation: visolex_records={len(visolex)} source_counts={source_counts}", quiet=args.quiet)

    rng = random.Random(args.seed)
    print("\nRandom samples:")
    for name, records in [*splits.items(), ("visolex", visolex)]:
        sample = rng.sample(records, min(args.samples, len(records))) if records else []
        print(f"[{name}]")
        for record in sample:
            # ASCII output prevents Windows cmd code-page errors while
            # preserving all Unicode in the actual JSONL artifact.
            print(json.dumps(record, ensure_ascii=True))
    log_event("DONE", f"Phase 1 validation: total_ids={len(all_ids)} status=passed", quiet=args.quiet)


if __name__ == "__main__":
    main()
