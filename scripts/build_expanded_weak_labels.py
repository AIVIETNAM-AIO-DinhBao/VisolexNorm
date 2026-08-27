"""Build the Phase 8 weak-label union from the frozen review namespace."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from build_weak_labels import WEAK_VALIDATOR, build_records, normalized_input_hash  # noqa: E402
from data_utils import read_jsonl  # noqa: E402
from phase3_utils import atomic_write_jsonl, load_json, sha256_file  # noqa: E402
from review_cache import ReviewCache  # noqa: E402
from review_candidates import validate_frozen_prompt, validate_manifest_scope  # noqa: E402
from select_review_manifest import assign_confidence_bands  # noqa: E402


def load_exclusion_ids(path: Path, expected_identity: str, expected_model: str) -> set[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Approved exclusions must be a JSON array")
    ids: set[str] = set()
    for row in payload:
        sample_id = row.get("id") if isinstance(row, dict) else None
        valid = (
            isinstance(sample_id, str)
            and row.get("status") == "approved_provider_exclusion"
            and row.get("review_identity_sha256") == expected_identity
            and row.get("llm_model") == expected_model
        )
        if not valid or sample_id in ids:
            raise ValueError("Approved exclusions contain an invalid or duplicate record")
        ids.add(sample_id)
    return ids


def validate_union(
    prior: list[dict[str, Any]], expanded: list[dict[str, Any]], protected_hashes: set[str]
) -> None:
    ids: set[str] = set()
    for row in expanded:
        WEAK_VALIDATOR.validate(row)
        sample_id = row["id"]
        if sample_id in ids:
            raise ValueError(f"Duplicate weak-label ID: {sample_id}")
        if normalized_input_hash(row["input_text"]) in protected_hashes:
            raise ValueError(f"Weak label overlaps ViLexNorm Dev/Test: {sample_id}")
        ids.add(sample_id)
    if expanded[: len(prior)] != prior:
        raise ValueError("Expanded pool must preserve the complete Phase 3 pool as its prefix")


def attach_confidence_bands(
    manifest: list[dict[str, Any]], candidates: list[dict[str, Any]], bands: list[str]
) -> list[dict[str, Any]]:
    by_source: dict[str, list[dict[str, Any]]] = {}
    for row in candidates:
        by_source.setdefault(row["original_source"], []).append(row)
    band_by_id: dict[str, str] = {}
    for source_rows in by_source.values():
        assigned = assign_confidence_bands(source_rows, bands)
        for band, rows in assigned.items():
            band_by_id.update({row["id"]: band for row in rows})
    missing = [row["id"] for row in manifest if row["id"] not in band_by_id]
    if missing:
        raise ValueError(f"Remaining manifest IDs absent from frozen candidates: {len(missing)}")
    return [{**row, "confidence_band": band_by_id[row["id"]]} for row in manifest]


def build_expanded_pool(root: Path, config_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    config = load_json(config_path)
    paths = {
        "manifest": root / config["remaining_manifest_path"],
        "cache": root / config["cache_path"],
        "exclusions": root / config["approved_exclusions_path"],
        "review_stats": root / config["review_stats_path"],
        "prior": root / config["phase3_weak_label_path"],
        "protected": root / config["protected_hashes_path"],
        "candidates": root / config["candidate_path"],
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing expanded-pool inputs: {missing}")

    manifest = read_jsonl(paths["manifest"])
    validate_manifest_scope(manifest, config)
    manifest = attach_confidence_bands(
        manifest, read_jsonl(paths["candidates"]), list(config["confidence_bands"])
    )
    stats = load_json(paths["review_stats"])
    prompt_hash = validate_frozen_prompt(config, root / config["frozen_prompt_path"])
    model = stats.get("llm_model")
    if stats.get("completion_status") != "completed_with_approved_provider_exclusions":
        raise ValueError("Expanded review has not reached an approved terminal status")
    if stats.get("review_identity_sha256") != prompt_hash or not isinstance(model, str):
        raise ValueError("Expanded review identity does not match the frozen prompt/policy")

    excluded_ids = load_exclusion_ids(paths["exclusions"], prompt_hash, model)
    if len(excluded_ids) != stats.get("provider_exclusion_count"):
        raise ValueError("Provider exclusion count does not match review statistics")
    cache = ReviewCache(paths["cache"])
    try:
        ids = [row["id"] for row in manifest]
        version = config["frozen_prompt_version"]
        reviews = cache.results_for_ids(ids, version, prompt_hash, model)
        if set(ids) - set(reviews) != excluded_ids:
            raise ValueError("Missing reviews do not exactly match approved exclusions")
        if cache.failed_count(version, prompt_hash, model):
            raise ValueError("Expanded review cache still contains unresolved failed batches")
    finally:
        cache.close()

    protected = {
        line.strip()
        for line in paths["protected"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    accepted, build_stats = build_records(
        manifest, reviews, protected, config, model, version, quiet=True, excluded_ids=excluded_ids
    )
    prior = read_jsonl(paths["prior"])
    if len(prior) != int(config["expected_phase3_weak_label_count"]):
        raise ValueError("Phase 3 weak-label count changed")
    expanded = prior + accepted
    validate_union(prior, expanded, protected)
    summary = {
        "phase": 8,
        "phase3_count": len(prior),
        "phase8_accepted_count": len(accepted),
        "expanded_count": len(expanded),
        "phase3_weak_label_sha256": sha256_file(paths["prior"]),
        "remaining_manifest_sha256": sha256_file(paths["manifest"]),
        "review_identity_sha256": prompt_hash,
        "llm_model": model,
        "review_decisions": stats["decision_counts"],
        "validation_drop_count": build_stats["validation_drop_count"],
        "validation_drop_counts": build_stats["drop_counts"],
    }
    return expanded, summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--config", type=Path, default=Path("configs/expanded_review_config.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config
    config = load_json(config_path)
    output = args.output or Path(config["expanded_weak_label_path"])
    output = output if output.is_absolute() else root / output
    rows, summary = build_expanded_pool(root, config_path)
    atomic_write_jsonl(rows, output)
    summary["expanded_weak_label_sha256"] = sha256_file(output)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()