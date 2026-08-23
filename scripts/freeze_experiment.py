"""Create or verify the immutable input manifest required before Phase 5 reads Test."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .data_utils import read_jsonl
    from .phase3_utils import canonical_json, sha256_file
except ImportError:
    from data_utils import read_jsonl
    from phase3_utils import canonical_json, sha256_file


def inventory(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.is_file():
        return {"kind": "file", "bytes": path.stat().st_size, "sha256": sha256_file(path)}
    files = [{"path": item.relative_to(path).as_posix(), "bytes": item.stat().st_size, "sha256": sha256_file(item)} for item in sorted(path.rglob("*")) if item.is_file()]
    if not files:
        raise ValueError(f"Artifact directory is empty: {path}")
    digest = hashlib.sha256(canonical_json(files).encode("utf-8")).hexdigest()
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
    return {"files": entries, "sha256": hashlib.sha256(canonical_json(entries).encode("utf-8")).hexdigest()}


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
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
    inputs = {
        name: {"declared_path": path.as_posix(), "inventory": inventory(path)}
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
        "test_order_sha256": hashlib.sha256(canonical_json(test_ids).encode("utf-8")).hexdigest(),
        "model_selection_rule": ["higher_f1", "lower_ERR", "model_a"],
        "metric_reference": metric_reference,
        "tokenizer_contract": tokenizer_a,
        "inputs": inputs,
    }


def verify_manifest(manifest: dict[str, Any], paths: dict[str, Path]) -> None:
    if manifest.get("status") != "frozen" or manifest.get("phase") != 5:
        raise ValueError("Manifest is not a frozen Phase 5 manifest")
    for name, path in paths.items():
        expected = manifest.get("inputs", {}).get(name, {}).get("inventory")
        if inventory(path) != expected:
            raise ValueError(f"Frozen artifact mismatch: {name}")
    tokenizer_a, tokenizer_b = tokenizer_inventory(paths["model_a_checkpoint"]), tokenizer_inventory(paths["model_b_checkpoint"])
    if tokenizer_a["sha256"] != tokenizer_b["sha256"] or tokenizer_a != manifest.get("tokenizer_contract"):
        raise ValueError("Frozen tokenizer contract mismatch")
    test_rows = read_jsonl(paths["test"])
    test_ids = [row.get("id") for row in test_rows]
    actual_order = hashlib.sha256(canonical_json(test_ids).encode("utf-8")).hexdigest()
    if len(test_ids) != manifest.get("expected_test_count") or actual_order != manifest.get("test_order_sha256"):
        raise ValueError("Frozen Test order or count mismatch")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/evaluation/freeze_manifest.json"))
    parser.add_argument("--model-a-checkpoint", type=Path, required=True)
    parser.add_argument("--model-b-checkpoint", type=Path, required=True)
    parser.add_argument("--test", type=Path, default=Path("data/processed/vilexnorm_test.jsonl"))
    parser.add_argument("--generation-config", type=Path, default=Path("configs/evaluation_generation_config.json"))
    parser.add_argument("--metric-code", type=Path, default=Path("scripts/evaluation_metrics.py"))
    parser.add_argument("--phase3-manifest", type=Path, default=Path("outputs/phase3_manifest.json"))
    parser.add_argument("--phase4-exit-report", type=Path, default=Path("outputs/model_b/phase4_exit_report.json"))
    parser.add_argument("--metric-reference", type=Path, default=Path("specs/005-experiment-evaluation/contracts/metric_reference.json"))
    parser.add_argument("--expected-test-count", type=int, default=1045)
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = {"model_a_checkpoint": args.model_a_checkpoint, "model_b_checkpoint": args.model_b_checkpoint, "test": args.test, "generation_config": args.generation_config, "metric_code": args.metric_code, "phase3_manifest": args.phase3_manifest, "phase4_exit_report": args.phase4_exit_report}
    if args.verify:
        manifest = json.loads(args.output.read_text(encoding="utf-8"))
        verify_manifest(manifest, paths)
        print(json.dumps({"verified": True, "manifest": str(args.output)}))
        return
    if args.output.exists():
        raise FileExistsError(f"Frozen manifest already exists: {args.output}; use --verify, never overwrite it")
    manifest = build_manifest(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"frozen": True, "manifest": str(args.output)}))


if __name__ == "__main__":
    main()