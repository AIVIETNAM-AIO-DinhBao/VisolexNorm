"""Run Model A candidate generation, review-manifest selection, and integrity audits."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

try:
    from scripts._bootstrap import ensure_project_root
except ModuleNotFoundError:
    from _bootstrap import ensure_project_root

ensure_project_root()

from visolexnorm.candidates.audit import audit_candidate_run
from visolexnorm.candidates.contracts import validate_inputs
from visolexnorm.candidates.generation import chunk_path, generate_chunk, load_completed_chunk, merge_chunks
from visolexnorm.candidates.manifests import build_remaining_report, select_remaining_review_manifest, select_stratified_review_manifest
from visolexnorm.common.artifacts import sha256_json
from visolexnorm.common.io import atomic_write_jsonl, load_json, read_jsonl
from visolexnorm.common.progress import ProgressReporter, log_event


ROOT = Path(__file__).parents[1]


def add_generate_parser(subparsers) -> None:
    parser = subparsers.add_parser("generate", help="Generate atomic Model A candidate chunks")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--chunk-dir", type=Path)
    parser.add_argument("--config", type=Path, default=Path("configs/candidate_generation_config.json"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.set_defaults(handler=run_generate)


def add_initial_manifest_parser(subparsers) -> None:
    parser = subparsers.add_parser("select-review", help="Select the deterministic Phase 3 review manifest")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/intermediate/visolex_review_manifest.jsonl"))
    parser.add_argument("--pilot-output", type=Path, default=Path("data/intermediate/visolex_pilot_manifest.jsonl"))
    parser.add_argument("--config", type=Path, default=Path("configs/llm_review_config.json"))
    parser.add_argument("--quiet", action="store_true")
    parser.set_defaults(handler=run_select_review)


def add_remaining_manifest_parser(subparsers) -> None:
    parser = subparsers.add_parser("select-remaining", help="Select the Phase 8 remaining review manifest")
    parser.add_argument("--config", type=Path, default=Path("configs/expanded_review_config.json"))
    parser.add_argument("--candidates", type=Path)
    parser.add_argument("--prior-manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    parser.set_defaults(handler=run_select_remaining)


def add_audit_parser(subparsers) -> None:
    parser = subparsers.add_parser("audit", help="Audit a completed 68,411-record candidate run")
    parser.add_argument("--input", type=Path, default=Path("data/processed/visolex_unlabeled.jsonl"))
    parser.add_argument("--candidates", type=Path, default=Path("data/intermediate/visolex_model_a_candidates.jsonl"))
    parser.add_argument("--chunk-dir", type=Path, default=Path("data/intermediate/candidate_chunks"))
    parser.add_argument("--manifest", type=Path, default=Path("data/intermediate/visolex_review_manifest.jsonl"))
    parser.add_argument("--config", type=Path, default=Path("configs/candidate_generation_config.json"))
    parser.add_argument("--candidate-zip", type=Path, default=Path("visolex_model_a_candidates.zip"))
    parser.add_argument("--model-zip", type=Path, default=Path("model_a_artifacts.zip"))
    parser.add_argument("--checkpoint", type=Path, default=Path("checkpoints/model_a"))
    parser.add_argument("--model-outputs", type=Path, default=Path("outputs/model_a"))
    parser.add_argument("--output", type=Path, default=Path("outputs/model_a/candidate_full_run_integrity.json"))
    parser.set_defaults(handler=run_audit)


def run_generate(args: argparse.Namespace) -> None:
    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    except ImportError as error:
        raise SystemExit("Install requirements-kaggle.txt before candidate generation.") from error
    config = load_json(args.config)
    config_hash = sha256_json(config)
    records = read_jsonl(args.input)
    validate_inputs(records)
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("--limit must be positive")
        records = records[:args.limit]
    if not args.checkpoint.is_dir():
        raise FileNotFoundError(f"Checkpoint directory does not exist: {args.checkpoint}")
    chunk_dir = args.chunk_dir or args.output.with_name(f"{args.output.stem}_chunks")
    chunk_dir.mkdir(parents=True, exist_ok=True)
    chunk_size = int(config["chunk_size"])
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(args.checkpoint)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.checkpoint).to(device)
    model.eval()
    total_chunks = math.ceil(len(records) / chunk_size)
    reporter = ProgressReporter("Model A candidate generation", len(records), quiet=args.quiet)
    log_event("START", f"Model A candidates: total={len(records)} chunks={total_chunks} chunk_size={chunk_size} batch_size={config['batch_size']} device={device} resume={args.resume}", quiet=args.quiet)
    skipped_chunks = 0
    empty_count = 0
    for chunk_index, start in enumerate(range(0, len(records), chunk_size)):
        expected = records[start:start + chunk_size]
        path = chunk_path(chunk_dir, chunk_index)
        existing = load_completed_chunk(path, expected, config_hash) if args.resume else None
        if existing is not None:
            skipped_chunks += 1
            empty_count += sum(row["generation_status"] == "empty_after_special_token_decode" for row in existing)
            reporter.advance(len(existing), f"chunk={chunk_index + 1}/{total_chunks} resumed")
            continue
        rows = generate_chunk(expected, tokenizer, model, device, config, config_hash, args.checkpoint.name)
        atomic_write_jsonl(rows, path)
        empty_count += sum(row["generation_status"] == "empty_after_special_token_decode" for row in rows)
        reporter.advance(len(rows), f"chunk={chunk_index + 1}/{total_chunks} committed")
    merge_chunks(records, chunk_dir, args.output, chunk_size, config_hash)
    reporter.done(f"resumed_chunks={skipped_chunks} empty_predictions={empty_count} output={args.output}")


def run_select_review(args: argparse.Namespace) -> None:
    config = load_json(args.config)
    candidates = read_jsonl(args.candidates)
    log_event("START", f"Review-manifest selection: candidates={len(candidates)} budget={config['review_budget']} seed={config['seed']}", quiet=args.quiet)
    manifest = select_stratified_review_manifest(candidates, config)
    pilot = [row for row in manifest if row["is_pilot"]]
    expected_pilot = int(config["pilot_per_stratum"]) * len({row["original_source"] for row in manifest}) * len(config["confidence_bands"])
    if len(pilot) != expected_pilot:
        raise RuntimeError(f"Pilot count mismatch: expected {expected_pilot}, found {len(pilot)}")
    atomic_write_jsonl(manifest, args.output)
    atomic_write_jsonl(pilot, args.pilot_output)
    log_event("PROGRESS", f"Review-manifest quotas: {dict(Counter(row['original_source'] for row in manifest))}", quiet=args.quiet)
    log_event("DONE", f"Review-manifest selection: manifest={len(manifest)} pilot={len(pilot)} output={args.output} pilot_output={args.pilot_output}", quiet=args.quiet)


def run_select_remaining(args: argparse.Namespace) -> None:
    config = load_json(args.config)
    candidates_path = args.candidates or Path(config["candidate_path"])
    prior_path = args.prior_manifest or Path(config["prior_manifest_path"])
    output_path = args.output or Path(config["remaining_manifest_path"])
    report_path = args.report or Path(config["remaining_manifest_report_path"])
    candidates = read_jsonl(candidates_path)
    prior = read_jsonl(prior_path)
    remaining = select_remaining_review_manifest(candidates, prior, config)
    atomic_write_jsonl(remaining, output_path)
    report = build_remaining_report(candidates_path, prior_path, output_path, candidates, prior, remaining)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"remaining_count": len(remaining), "output": str(output_path)}, ensure_ascii=False))


def run_audit(args: argparse.Namespace) -> None:
    schema = load_json(ROOT / "specs/003-weak-labeling-llm-review/contracts/candidate.schema.json")
    report = audit_candidate_run(
        input_path=args.input, candidates_path=args.candidates, chunk_dir=args.chunk_dir,
        manifest_path=args.manifest, config_path=args.config, candidate_zip=args.candidate_zip,
        model_zip=args.model_zip, checkpoint=args.checkpoint, model_outputs=args.model_outputs,
        candidate_schema=schema,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Candidate full-run integrity: passed={report['passed']} output={args.output}")
    if not report["passed"]:
        failed = [name for name, passed in report["checks"].items() if not passed]
        raise SystemExit(f"Candidate integrity audit failed: {failed}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_generate_parser(subparsers)
    add_initial_manifest_parser(subparsers)
    add_remaining_manifest_parser(subparsers)
    add_audit_parser(subparsers)
    args = parser.parse_args()
    try:
        args.handler(args)
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()