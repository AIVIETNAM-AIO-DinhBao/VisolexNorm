"""Generate resumable Model A normalization candidates for ViSoLex on Kaggle GPU.

Example (Kaggle):
python scripts/generate_model_a_candidates.py \
  --input /kaggle/input/visolexnorm-processed/visolex_unlabeled.jsonl \
  --checkpoint /kaggle/input/model-a-artifacts/model_a \
  --output /kaggle/working/data/intermediate/visolex_model_a_candidates.jsonl \
  --config configs/model_a_generation_config.json --resume
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import sys

sys.path.insert(0, str(Path(__file__).parent))
from data_utils import read_jsonl, write_jsonl  # noqa: E402


REQUIRED_INPUT = {"id", "dataset", "original_source", "input_text"}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_input(records: list[dict[str, Any]]) -> None:
    ids: set[str] = set()
    for index, record in enumerate(records, 1):
        if not REQUIRED_INPUT <= record.keys() or record["dataset"] != "ViSoLex":
            raise ValueError(f"Invalid ViSoLex record at line {index}")
        if not isinstance(record["input_text"], str) or not record["input_text"]:
            raise ValueError(f"Empty input_text at line {index}")
        if record["id"] in ids:
            raise ValueError(f"Duplicate input ID: {record['id']}")
        ids.add(record["id"])


def read_completed(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    completed: dict[str, dict[str, Any]] = {}
    for record in read_jsonl(path):
        sample_id = record.get("id")
        if not isinstance(sample_id, str) or sample_id in completed:
            raise ValueError(f"Invalid or duplicate candidate ID in existing output: {sample_id!r}")
        completed[sample_id] = record
    return completed


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Model A candidates for ViSoLex.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/model_a_generation_config.json"))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--limit", type=int, help="Small deterministic prefix for smoke testing")
    args = parser.parse_args()

    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    except ImportError as error:
        raise SystemExit("Install requirements-kaggle.txt before running this script.") from error

    config = load_json(args.config)
    records = read_jsonl(args.input)
    validate_input(records)
    if args.limit is not None:
        records = records[: args.limit]
    if not args.checkpoint.is_dir():
        raise FileNotFoundError(f"Checkpoint directory does not exist: {args.checkpoint}")

    if args.output.exists() and not args.resume:
        raise FileExistsError(f"{args.output} exists; pass --resume or choose another output path")
    completed = read_completed(args.output) if args.resume else {}
    expected_ids = {record["id"] for record in records}
    unknown = set(completed) - expected_ids
    if unknown:
        raise ValueError(f"Existing output contains IDs outside requested input: {sorted(unknown)[:3]}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(args.checkpoint)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.checkpoint).to(device)
    model.eval()
    pending = [record for record in records if record["id"] not in completed]
    batch_size = int(config["batch_size"])
    args.output.parent.mkdir(parents=True, exist_ok=True)

    for start in range(0, len(pending), batch_size):
        batch = pending[start : start + batch_size]
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
        transition_scores = model.compute_transition_scores(
            generated.sequences,
            generated.scores,
            beam_indices=generated.beam_indices,
            normalize_logits=True,
        )
        # Each score column corresponds to one generated decoding step. Averaging
        # token log-probabilities makes scores comparable across output lengths.
        generated_mask = transition_scores.ne(0)
        confidence = (
            transition_scores.sum(dim=1) / generated_mask.sum(dim=1).clamp(min=1)
        ).detach().cpu().tolist()
        decoded = tokenizer.batch_decode(generated.sequences, skip_special_tokens=True)
        with args.output.open("a", encoding="utf-8", newline="\n") as handle:
            for record, candidate, score in zip(batch, decoded, confidence):
                result = {
                    "id": record["id"],
                    "dataset": "ViSoLex",
                    "original_source": record["original_source"],
                    "input_text": record["input_text"],
                    "candidate_text": candidate.strip(),
                    "model_a_confidence": float(score),
                    "candidate_checkpoint": args.checkpoint.name,
                    "generation_config_version": config["generation_config_version"],
                    "confidence_rule": config["confidence_rule"],
                }
                handle.write(json.dumps(result, ensure_ascii=False) + "\n")
                completed[result["id"]] = result
        print(f"Generated {min(start + len(batch), len(pending))}/{len(pending)} pending candidates")

    # A completed interrupted run is rewritten in original corpus order.
    if set(completed) != expected_ids:
        raise RuntimeError("Candidate generation ended with missing IDs")
    write_jsonl((completed[record["id"]] for record in records), args.output)
    print(f"Saved {len(records)} candidates to {args.output} on {device}")


if __name__ == "__main__":
    main()