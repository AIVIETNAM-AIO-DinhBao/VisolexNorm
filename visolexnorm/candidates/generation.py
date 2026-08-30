"""Atomic, resumable Model A candidate generation primitives."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Iterable

from visolexnorm.candidates.contracts import validate_candidate
from visolexnorm.common.io import atomic_write_jsonl, read_jsonl


def chunk_path(chunk_dir: Path, chunk_index: int) -> Path:
    return chunk_dir / f"candidates_{chunk_index:06d}.jsonl"


def load_completed_chunk(path: Path, expected_records: list[dict[str, Any]], config_hash: str) -> list[dict[str, Any]] | None:
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
    generated_tokens = sequences[:, -transition_scores.shape[1]:]
    if pad_token_id is None:
        return transition_scores.new_ones(transition_scores.shape, dtype=bool)
    return generated_tokens.ne(pad_token_id)


def iter_batches(values: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for start in range(0, len(values), size):
        yield values[start:start + size]


def generate_chunk(records, tokenizer, model, device, config, config_hash, checkpoint_id):
    """Generate one chunk and preserve the frozen candidate record field order."""
    import torch

    results: list[dict[str, Any]] = []
    for batch in iter_batches(records, int(config["batch_size"])):
        encoded = tokenizer(
            [record["input_text"] for record in batch],
            max_length=int(config["max_source_length"]),
            truncation=True,
            padding=True,
            return_tensors="pt",
        ).to(device)
        with torch.inference_mode():
            generated = model.generate(
                **encoded,
                num_beams=int(config["num_beams"]),
                max_new_tokens=int(config["max_new_tokens"]),
                length_penalty=float(config["length_penalty"]),
                early_stopping=bool(config["early_stopping"]),
                return_dict_in_generate=True,
                output_scores=True,
            )
        scores = model.compute_transition_scores(
            generated.sequences,
            generated.scores,
            beam_indices=generated.beam_indices,
            normalize_logits=True,
        )
        mask = generated_token_mask(generated.sequences, scores, tokenizer.pad_token_id)
        token_counts = mask.sum(dim=1)
        confidences = ((scores * mask).sum(dim=1) / token_counts.clamp(min=1)).detach().cpu().tolist()
        decoded = tokenizer.batch_decode(generated.sequences, skip_special_tokens=True)
        for source, candidate, confidence, token_count in zip(batch, decoded, confidences, token_counts.detach().cpu().tolist()):
            candidate = candidate.strip()
            if not math.isfinite(float(confidence)) or int(token_count) < 1:
                raise RuntimeError(f"Invalid generation output for {source['id']}")
            generation_status = "generated_text" if candidate else "empty_after_special_token_decode"
            results.append({
                "id": source["id"],
                "dataset": "ViSoLex",
                "original_source": source["original_source"],
                "input_text": source["input_text"],
                "candidate_text": candidate,
                "model_a_confidence": float(confidence),
                "candidate_checkpoint": checkpoint_id,
                "generation_config_hash": config_hash,
                "sequence_token_count": int(token_count),
                "generation_status": generation_status,
            })
    return results


def merge_chunks(records, chunk_dir: Path, output: Path, chunk_size: int, config_hash: str) -> None:
    """Validate and merge committed chunks in original corpus order."""
    merged = []
    for chunk_index, start in enumerate(range(0, len(records), chunk_size)):
        expected = records[start:start + chunk_size]
        rows = load_completed_chunk(chunk_path(chunk_dir, chunk_index), expected, config_hash)
        if rows is None:
            raise RuntimeError(f"Chunk {chunk_index} is missing or invalid")
        merged.extend(rows)
    if [row["id"] for row in merged] != [row["id"] for row in records]:
        raise RuntimeError("Merged candidates do not preserve input order")
    atomic_write_jsonl(merged, output)