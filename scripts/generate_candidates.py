"""Generate Model A candidates in atomic, resumable chunks on Kaggle GPU."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).parent))
from data_utils import read_jsonl  # noqa: E402
from phase3_utils import ProgressReporter, atomic_write_jsonl, ensure_finite_number, load_json, log_event, sha256_json  # noqa: E402


REQUIRED_INPUT = {"id", "dataset", "original_source", "input_text"}
REQUIRED_CANDIDATE = {
    "id", "dataset", "original_source", "input_text", "candidate_text",
    "model_a_confidence", "candidate_checkpoint", "generation_config_hash",
    "sequence_token_count", "generation_status",
}

GENERATION_STATUSES = {"generated_text", "empty_after_special_token_decode"}


def validate_inputs(records: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for line_number, record in enumerate(records, start=1):
        if not REQUIRED_INPUT <= record.keys() or record.get("dataset") != "ViSoLex":
            raise ValueError(f"Invalid ViSoLex input at line {line_number}")
        if not isinstance(record.get("input_text"), str) or not record["input_text"]:
            raise ValueError(f"Empty input_text at line {line_number}")
        sample_id = record.get("id")
        if not isinstance(sample_id, str) or not sample_id or sample_id in seen:
            raise ValueError(f"Invalid or duplicate ID at line {line_number}: {sample_id!r}")
        seen.add(sample_id)


def validate_candidate(record: dict[str, Any], expected: dict[str, Any], config_hash: str) -> None:
    if set(record) != REQUIRED_CANDIDATE:
        raise ValueError(f"Candidate fields do not match contract for {expected['id']}")
    for field in ("id", "dataset", "original_source", "input_text"):
        if record[field] != expected[field]:
            raise ValueError(f"Candidate {expected['id']} changed field {field}")
    if not isinstance(record["candidate_text"], str):
        raise ValueError(f"Candidate text is not a string for {expected['id']}")
    if record.get("generation_status") not in GENERATION_STATUSES:
        raise ValueError(f"Invalid generation_status for {expected['id']}")
    if bool(record["candidate_text"]) != (record["generation_status"] == "generated_text"):
        raise ValueError(f"Candidate text/status mismatch for {expected['id']}")
    ensure_finite_number(record["model_a_confidence"], "model_a_confidence")
    if record["generation_config_hash"] != config_hash:
        raise ValueError(f"Candidate config hash mismatch for {expected['id']}")
    if not isinstance(record["sequence_token_count"], int) or record["sequence_token_count"] < 1:
        raise ValueError(f"Invalid sequence_token_count for {expected['id']}")


def chunk_path(chunk_dir: Path, chunk_index: int) -> Path:
    return chunk_dir / f"candidates_{chunk_index:06d}.jsonl"


def load_completed_chunk(
    path: Path, expected_records: list[dict[str, Any]], config_hash: str
) -> list[dict[str, Any]] | None:
    if not path.is_file():
        return None
    rows = read_jsonl(path)
    if len(rows) != len(expected_records):
        return None
    try:
        for row, expected in zip(rows, expected_records):
            validate_candidate(row, expected, config_hash)
    except ValueError:
        return None
    return rows


def generated_token_mask(sequences: Any, transition_scores: Any, pad_token_id: int | None) -> Any:
    """Mask padding while retaining EOS and legitimate zero-log-probability tokens."""
    generated_tokens = sequences[:, -transition_scores.shape[1] :]
    if pad_token_id is None:
        return transition_scores.new_ones(transition_scores.shape, dtype=bool)
    return generated_tokens.ne(pad_token_id)


def iter_batches(values: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def generate_chunk(records, tokenizer, model, device, config, config_hash, checkpoint_id):
    import torch

    results: list[dict[str, Any]] = []
    for batch in iter_batches(records, int(config["batch_size"])):
        encoded = tokenizer(
            [record["input_text"] for record in batch],
            max_length=int(config["max_source_length"]), truncation=True,
            padding=True, return_tensors="pt",
        ).to(device)
        with torch.inference_mode():
            generated = model.generate(
                **encoded, num_beams=int(config["num_beams"]),
                max_new_tokens=int(config["max_new_tokens"]),
                length_penalty=float(config["length_penalty"]),
                early_stopping=bool(config["early_stopping"]),
                return_dict_in_generate=True, output_scores=True,
            )
        scores = model.compute_transition_scores(
            generated.sequences, generated.scores,
            beam_indices=generated.beam_indices, normalize_logits=True,
        )
        mask = generated_token_mask(generated.sequences, scores, tokenizer.pad_token_id)
        token_counts = mask.sum(dim=1)
        confidences = ((scores * mask).sum(dim=1) / token_counts.clamp(min=1)).detach().cpu().tolist()
        decoded = tokenizer.batch_decode(generated.sequences, skip_special_tokens=True)
        for source, candidate, confidence, token_count in zip(
            batch, decoded, confidences, token_counts.detach().cpu().tolist()
        ):
            candidate = candidate.strip()
            if not math.isfinite(float(confidence)) or int(token_count) < 1:
                raise RuntimeError(f"Invalid generation output for {source['id']}")
            generation_status = "generated_text" if candidate else "empty_after_special_token_decode"
            results.append({
                "id": source["id"], "dataset": "ViSoLex",
                "original_source": source["original_source"], "input_text": source["input_text"],
                "candidate_text": candidate, "model_a_confidence": float(confidence),
                "candidate_checkpoint": checkpoint_id, "generation_config_hash": config_hash,
                "sequence_token_count": int(token_count), "generation_status": generation_status,
            })
    return results


def merge_chunks(records, chunk_dir, output, chunk_size, config_hash) -> None:
    merged = []
    for chunk_index, start in enumerate(range(0, len(records), chunk_size)):
        expected = records[start : start + chunk_size]
        rows = load_completed_chunk(chunk_path(chunk_dir, chunk_index), expected, config_hash)
        if rows is None:
            raise RuntimeError(f"Chunk {chunk_index} is missing or invalid")
        merged.extend(rows)
    if [row["id"] for row in merged] != [row["id"] for row in records]:
        raise RuntimeError("Merged candidates do not preserve input order")
    atomic_write_jsonl(merged, output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate atomic Model A candidate chunks.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--chunk-dir", type=Path)
    parser.add_argument("--config", type=Path, default=Path("configs/candidate_generation_config.json"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--quiet", action="store_true", help="Suppress operational progress logs")
    args = parser.parse_args()

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
        records = records[: args.limit]
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
        expected = records[start : start + chunk_size]
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


if __name__ == "__main__":
    main()