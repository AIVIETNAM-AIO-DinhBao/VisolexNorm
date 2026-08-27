"""Audit the completed Model A candidate run without rerunning GPU inference."""

from __future__ import annotations

import argparse
import json
import math
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

try:
    from scripts._bootstrap import ensure_project_root
except ModuleNotFoundError:
    from _bootstrap import ensure_project_root

ensure_project_root()

from visolexnorm.common.artifacts import sha256_file, sha256_json
from visolexnorm.common.io import load_json, read_jsonl


ROOT = Path(__file__).parents[1]
CANDIDATE_VALIDATOR = Draft202012Validator(load_json(
    ROOT / "specs/003-weak-labeling-llm-review/contracts/candidate.schema.json"
))


def audit(args: argparse.Namespace) -> dict[str, Any]:
    config = load_json(args.config)
    config_hash = sha256_json(config)
    inputs = read_jsonl(args.input)
    candidates = read_jsonl(args.candidates)
    manifest = read_jsonl(args.manifest)
    expected_chunks = math.ceil(len(inputs) / int(config["chunk_size"]))
    chunk_paths = sorted(args.chunk_dir.glob("candidates_*.jsonl"))

    schema_errors: list[str] = []
    non_finite_confidence = 0
    for index, row in enumerate(candidates, start=1):
        errors = list(CANDIDATE_VALIDATOR.iter_errors(row))
        if errors and len(schema_errors) < 10:
            schema_errors.append(f"line {index}: {errors[0].message}")
        confidence = row.get("model_a_confidence")
        if not isinstance(confidence, (int, float)) or not math.isfinite(confidence):
            non_finite_confidence += 1

    chunk_rows: list[dict[str, Any]] = []
    chunk_counts: list[int] = []
    for path in chunk_paths:
        rows = read_jsonl(path)
        chunk_rows.extend(rows)
        chunk_counts.append(len(rows))

    input_ids = [row["id"] for row in inputs]
    candidate_ids = [row["id"] for row in candidates]
    candidate_id_set = set(candidate_ids)
    expected_chunk_names = [f"candidates_{index:06d}.jsonl" for index in range(expected_chunks)]
    actual_chunk_names = [path.name for path in chunk_paths]
    generation_hashes = sorted({row.get("generation_config_hash") for row in candidates})
    checkpoint_labels = sorted({row.get("candidate_checkpoint") for row in candidates})
    status_counts = Counter(row.get("generation_status") for row in candidates)

    zip_error = None
    zip_members = 0
    try:
        with zipfile.ZipFile(args.candidate_zip) as archive:
            zip_error = archive.testzip()
            zip_members = len(archive.infolist())
    except (OSError, zipfile.BadZipFile) as error:
        zip_error = str(error)

    checks = {
        "input_count_68411": len(inputs) == 68411,
        "candidate_count_68411": len(candidates) == 68411,
        "input_ids_unique": len(set(input_ids)) == len(input_ids),
        "candidate_ids_unique": len(candidate_id_set) == len(candidate_ids),
        "candidate_ids_and_order_match_input": candidate_ids == input_ids,
        "candidate_provenance_matches_input": len(inputs) == len(candidates) and all(
            candidate.get(field) == source.get(field)
            for source, candidate in zip(inputs, candidates)
            for field in ("id", "dataset", "original_source", "input_text")
        ),
        "candidate_schema_valid": not schema_errors,
        "confidence_finite": non_finite_confidence == 0,
        "generation_config_hash_matches": generation_hashes == [config_hash],
        "chunk_count_matches": len(chunk_paths) == expected_chunks,
        "chunk_names_contiguous": actual_chunk_names == expected_chunk_names,
        "chunk_sizes_match": chunk_counts == [
            min(int(config["chunk_size"]), len(inputs) - start)
            for start in range(0, len(inputs), int(config["chunk_size"]))
        ],
        "chunks_equal_merged_candidates": chunk_rows == candidates,
        "manifest_count_20000": len(manifest) == 20000,
        "manifest_ids_unique": len({row["id"] for row in manifest}) == len(manifest),
        "manifest_is_candidate_subset": {row["id"] for row in manifest} <= candidate_id_set,
        "candidate_zip_crc_valid": zip_error is None,
        "model_checkpoint_present": (args.checkpoint / "model.safetensors").is_file(),
        "model_outputs_present": all(path.is_file() for path in (
            args.model_outputs / "dev_predictions.jsonl",
            args.model_outputs / "dev_metrics.json",
            args.model_outputs / "train_config.json",
        )),
    }
    return {
        "passed": all(checks.values()),
        "evidence_type": "completed_full_run_integrity_audit",
        "approved_smoke_test_replacement": True,
        "checks": checks,
        "counts": {
            "inputs": len(inputs),
            "candidates": len(candidates),
            "manifest": len(manifest),
            "chunks": len(chunk_paths),
            "candidate_zip_members": zip_members,
            "non_finite_confidence": non_finite_confidence,
            "generation_status": dict(sorted(status_counts.items())),
        },
        "generation": {
            "config_path": args.config.as_posix(),
            "config_sha256": sha256_file(args.config),
            "canonical_config_hash": config_hash,
            "recorded_config_hashes": generation_hashes,
            "checkpoint_labels": checkpoint_labels,
        },
        "artifacts": {
            "candidate_jsonl_sha256": sha256_file(args.candidates),
            "candidate_zip_sha256": sha256_file(args.candidate_zip),
            "model_artifacts_zip_sha256": sha256_file(args.model_zip),
            "model_safetensors_sha256": sha256_file(args.checkpoint / "model.safetensors"),
            "manifest_sha256": sha256_file(args.manifest),
        },
        "diagnostics": {
            "schema_errors_first_10": schema_errors,
            "candidate_zip_error": zip_error,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit the completed 68,411-record candidate run.")
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
    args = parser.parse_args()
    report = audit(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Candidate full-run integrity: passed={report['passed']} output={args.output}")
    if not report["passed"]:
        failed = [name for name, passed in report["checks"].items() if not passed]
        raise SystemExit(f"Candidate integrity audit failed: {failed}")


if __name__ == "__main__":
    main()