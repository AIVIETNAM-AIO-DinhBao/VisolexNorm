"""Create or verify the immutable input manifest required before Phase 5 reads Test."""
from __future__ import annotations

import json
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from visolexnorm.common.artifacts import canonical_json, sha256_bytes, sha256_file, sha256_text
from visolexnorm.common.io import read_jsonl


def inventory(path: Path, *, normalize_text: bool = False) -> dict[str, Any]:
    """Fingerprint an artifact, optionally normalizing UTF-8 line endings.

    Checkpoints and datasets remain byte-for-byte frozen. Source/config text is
    normalized only to make a Windows-created freeze manifest verifiable from
    the same Git revision on Kaggle's Linux filesystem.
    """
    if not path.exists():
        raise FileNotFoundError(path)
    if path.is_file():
        if normalize_text:
            content = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            return {"kind": "file", "bytes": len(content), "sha256": sha256_bytes(content), "line_endings_normalized": "LF"}
        return {"kind": "file", "bytes": path.stat().st_size, "sha256": sha256_file(path)}
    files = [{"path": item.relative_to(path).as_posix(), "bytes": item.stat().st_size, "sha256": sha256_file(item)} for item in sorted(path.rglob("*")) if item.is_file()]
    if not files:
        raise ValueError(f"Artifact directory is empty: {path}")
    digest = sha256_text(canonical_json(files))
    return {"kind": "directory", "files": files, "file_count": len(files), "sha256": digest}


def tokenizer_inventory(checkpoint: Path) -> dict[str, Any]:
    """Fingerprint tokenizer vocabulary assets, not checkpoint-specific metadata paths."""
    if not checkpoint.is_dir():
        raise ValueError(f"Checkpoint is not a directory: {checkpoint}")
    vocabulary_names = {"sentencepiece.bpe.model", "dict.txt", "vocab.json", "merges.txt", "spiece.model"}
    files = [item for item in sorted(checkpoint.rglob("*")) if item.is_file() and item.name in vocabulary_names]
    if not files:
        raise ValueError(f"Checkpoint has no tokenizer files: {checkpoint}")
    entries = [{"path": item.relative_to(checkpoint).as_posix(), "bytes": item.stat().st_size, "sha256": sha256_file(item)} for item in files]
    return {"files": entries, "sha256": sha256_text(canonical_json(entries))}


def build_manifest(args: Namespace) -> dict[str, Any]:
    test_rows = read_jsonl(args.test)
    test_ids = [row.get("id") for row in test_rows]
    if len(test_rows) != args.expected_test_count or len(test_ids) != len(set(test_ids)):
        raise ValueError(f"Test must contain exactly {args.expected_test_count} unique IDs")
    if any(row.get("dataset") != "ViLexNorm" or row.get("split") != "test" for row in test_rows):
        raise ValueError("Test records must be ViLexNorm test records")
    metric_reference = json.loads(args.metric_reference.read_text(encoding="utf-8"))
    paths = {
        "model_a_checkpoint": args.model_a_checkpoint,
        "model_b_checkpoint": args.model_b_checkpoint,
        "test": args.test,
        "generation_config": args.generation_config,
        "metric_code": args.metric_code,
        "phase3_manifest": args.phase3_manifest,
        "phase4_exit_report": args.phase4_exit_report,
    }
    text_artifacts = {"generation_config", "metric_code"}
    inputs = {
        name: {"declared_path": path.as_posix(), "inventory": inventory(path, normalize_text=name in text_artifacts)}
        for name, path in paths.items()
    }
    tokenizer_a, tokenizer_b = tokenizer_inventory(args.model_a_checkpoint), tokenizer_inventory(args.model_b_checkpoint)
    if tokenizer_a["sha256"] != tokenizer_b["sha256"]:
        raise ValueError("Model A/B tokenizer contracts differ; Phase 5 requires one tokenizer contract")
    return {
        "schema_version": 1,
        "phase": 5,
        "status": "frozen",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": 2026,
        "expected_test_count": args.expected_test_count,
        "test_order_sha256": sha256_text(canonical_json(test_ids)),
        "model_selection_rule": ["higher_f1", "higher_ERR", "model_a"],
        "metric_reference": metric_reference,
        "tokenizer_contract": tokenizer_a,
        "inputs": inputs,
    }


def verify_manifest(manifest: dict[str, Any], paths: dict[str, Path]) -> None:
    if manifest.get("status") != "frozen" or manifest.get("phase") != 5:
        raise ValueError("Manifest is not a frozen Phase 5 manifest")
    text_artifacts = {"generation_config", "metric_code"}
    for name, path in paths.items():
        expected = manifest.get("inputs", {}).get(name, {}).get("inventory")
        if inventory(path, normalize_text=name in text_artifacts) != expected:
            raise ValueError(f"Frozen artifact mismatch: {name}")
    tokenizer_a, tokenizer_b = tokenizer_inventory(paths["model_a_checkpoint"]), tokenizer_inventory(paths["model_b_checkpoint"])
    if tokenizer_a["sha256"] != tokenizer_b["sha256"] or tokenizer_a != manifest.get("tokenizer_contract"):
        raise ValueError("Frozen tokenizer contract mismatch")
    test_rows = read_jsonl(paths["test"])
    test_ids = [row.get("id") for row in test_rows]
    actual_order = sha256_text(canonical_json(test_ids))
    if len(test_ids) != manifest.get("expected_test_count") or actual_order != manifest.get("test_order_sha256"):
        raise ValueError("Frozen Test order or count mismatch")
