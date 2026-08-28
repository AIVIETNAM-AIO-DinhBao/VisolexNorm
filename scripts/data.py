"""Run ViLexNorm and ViSoLex data preparation, validation, and hash export."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

try:
    from scripts._bootstrap import ensure_project_root
except ModuleNotFoundError:
    from _bootstrap import ensure_project_root

ensure_project_root()

from visolexnorm.common.io import read_jsonl, write_jsonl
from visolexnorm.common.progress import log_event
from visolexnorm.data.preparation import (
    SourceSpec,
    prepare_vilexnorm_split,
    prepare_visolex_corpus,
    protected_texts,
    validate_source_specs,
)
from visolexnorm.data.validation import build_protected_hashes, validate_processed_data


def add_prepare_vilexnorm_parser(subparsers) -> None:
    parser = subparsers.add_parser("prepare-vilexnorm", help="Prepare ViLexNorm processed JSONL files")
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--dev", type=Path, required=True)
    parser.add_argument("--test", type=Path, required=True)
    parser.add_argument("--input-field", required=True)
    parser.add_argument("--target-field", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--log-every", type=int, default=5000)
    parser.add_argument("--quiet", action="store_true")
    parser.set_defaults(handler=run_prepare_vilexnorm)


def add_prepare_visolex_parser(subparsers) -> None:
    parser = subparsers.add_parser("prepare-visolex", help="Prepare canonical ViSoLex unlabeled JSONL")
    parser.add_argument("--source", action="append", nargs=3, metavar=("NAME", "RAW_FILE", "TEXT_FIELD"), required=True)
    parser.add_argument("--vilexnorm-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--log-every", type=int, default=5000)
    parser.add_argument("--quiet", action="store_true")
    parser.set_defaults(handler=run_prepare_visolex)


def add_validate_parser(subparsers) -> None:
    parser = subparsers.add_parser("validate", help="Validate processed Phase 1 artifacts")
    parser.add_argument("--data-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--quiet", action="store_true")
    parser.set_defaults(handler=run_validate)


def add_hash_parser(subparsers) -> None:
    parser = subparsers.add_parser("export-protected-hashes", help="Export Dev/Test input SHA-256 fingerprints")
    parser.add_argument("--data-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/vilexnorm_protected_input_hashes.txt"))
    parser.add_argument("--quiet", action="store_true")
    parser.set_defaults(handler=run_export_protected_hashes)


def event_logger(quiet: bool):
    return lambda event, message: log_event(event, message, quiet=quiet)


def run_prepare_vilexnorm(args: argparse.Namespace) -> None:
    log = event_logger(args.quiet)
    for split, raw_path in (("train", args.train), ("dev", args.dev), ("test", args.test)):
        if not raw_path.is_file():
            raise ValueError(f"Raw {split} file does not exist: {raw_path}")
        log("START", f"ViLexNorm preprocessing: split={split} input={raw_path}")
        result = prepare_vilexnorm_split(raw_path, split, args.input_field, args.target_field, log_every=args.log_every, log=log)
        output = args.output_dir / f"vilexnorm_{split}.jsonl"
        write_jsonl(result.records, output)
        log("DONE", f"ViLexNorm preprocessing: split={split} raw={len(result.records) + result.skipped_empty} kept={len(result.records)} skipped_empty={result.skipped_empty} output={output}")


def run_prepare_visolex(args: argparse.Namespace) -> None:
    log = event_logger(args.quiet)
    sources = [SourceSpec(name, Path(raw_file), text_field) for name, raw_file, text_field in args.source]
    validate_source_specs(sources)
    result = prepare_visolex_corpus(sources, protected_texts(args.vilexnorm_dir), log_every=args.log_every, log=log)
    output = args.output_dir / "visolex_unlabeled.jsonl"
    write_jsonl(result.records, output)
    log("DONE", f"ViSoLex preprocessing: total={len(result.records)} output={output}")


def run_validate(args: argparse.Namespace) -> None:
    log = event_logger(args.quiet)
    log("START", f"Phase 1 validation: data_dir={args.data_dir}")
    report = validate_processed_data(args.data_dir)
    for split, count in report.split_counts.items():
        log("PROGRESS", f"Phase 1 validation: split={split} records={count}")
    log("PROGRESS", f"Phase 1 validation: visolex_records={sum(report.source_counts.values())} source_counts={report.source_counts}")
    rng = random.Random(args.seed)
    print("\nRandom samples:")
    for name in ("train", "dev", "test", "visolex"):
        path = args.data_dir / (f"vilexnorm_{name}.jsonl" if name != "visolex" else "visolex_unlabeled.jsonl")
        rows = read_jsonl(path)
        print(f"[{name}]")
        for row in rng.sample(rows, min(args.samples, len(rows))) if rows else []:
            print(json.dumps(row, ensure_ascii=True))
    log("DONE", f"Phase 1 validation: total_ids={report.total_ids} status=passed")


def run_export_protected_hashes(args: argparse.Namespace) -> None:
    log = event_logger(args.quiet)
    log("START", f"Protected-hash export: data_dir={args.data_dir}")
    hashes = build_protected_hashes(args.data_dir)
    for split in ("dev", "test"):
        path = args.data_dir / f"vilexnorm_{split}.jsonl"
        count = len(read_jsonl(path))
        log("PROGRESS", f"Protected-hash export: split={split} records={count} unique_hashes={len(hashes)}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(hashes) + "\n", encoding="utf-8")
    log("DONE", f"Protected-hash export: fingerprints={len(hashes)} output={args.output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_prepare_vilexnorm_parser(subparsers)
    add_prepare_visolex_parser(subparsers)
    add_validate_parser(subparsers)
    add_hash_parser(subparsers)
    args = parser.parse_args()
    try:
        args.handler(args)
    except (FileNotFoundError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()