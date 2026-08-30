"""Deterministic Model B and Model C mixture construction."""

from __future__ import annotations

import json
import math
import random
from collections import Counter
from pathlib import Path
from typing import Any

from visolexnorm.common.artifacts import sha256_bytes, sha256_file
from visolexnorm.common.io import load_json, read_jsonl


def validate_records(
    gold: list[dict[str, Any]],
    dev: list[dict[str, Any]],
    pseudo: list[dict[str, Any]],
    prompt: str,
) -> None:
    """Validate shared Train, Dev, and reviewed pseudo-label contracts."""
    for rows, split in ((gold, "train"), (dev, "dev")):
        if len({row.get("id") for row in rows}) != len(rows):
            raise ValueError(f"Duplicate {split} ID")
        if any(
            row.get("dataset") != "ViLexNorm"
            or row.get("split") != split
            or row.get("label_source") != "human"
            or not row.get("input_text")
            or not row.get("target_text")
            for row in rows
        ):
            raise ValueError(f"Invalid ViLexNorm {split} record")
    if {row["id"] for row in gold} & {row["id"] for row in dev}:
        raise ValueError("Train/Dev ID overlap")
    if len({row.get("id") for row in pseudo}) != len(pseudo):
        raise ValueError("Duplicate pseudo ID")
    if any(
        row.get("dataset") != "ViSoLex"
        or row.get("label_source") != "model_a+llm_review"
        or row.get("llm_decision") not in {"KEEP", "EDIT"}
        or row.get("accepted") is not True
        or row.get("prompt_version") != prompt
        or not row.get("target_text")
        for row in pseudo
    ):
        raise ValueError("Invalid weak-label record")


def sample_model_b_epochs(
    gold_ids: list[str],
    pseudo_ids: list[str],
    *,
    seed: int,
    num_epochs: int,
    pseudo_per_epoch: int,
) -> tuple[list[dict[str, Any]], bool]:
    """Preserve the frozen Model B unseen-first sampling sequence."""
    if not gold_ids or not pseudo_ids:
        raise ValueError("Pools must be non-empty")
    gold_ids, pseudo_ids = sorted(gold_ids), sorted(pseudo_ids)
    unseen, seen, epochs = list(pseudo_ids), [], []
    replacement = len(pseudo_ids) < pseudo_per_epoch
    for epoch_index in range(num_epochs):
        rng = random.Random(seed + epoch_index)
        candidates = list(unseen)
        rng.shuffle(candidates)
        chosen = candidates[:pseudo_per_epoch]
        remaining = pseudo_per_epoch - len(chosen)
        if remaining and not replacement:
            reused = list(seen)
            rng.shuffle(reused)
            chosen.extend(reused[:remaining])
        while remaining and replacement:
            refill = list(pseudo_ids)
            rng.shuffle(refill)
            take = min(remaining, len(refill))
            chosen.extend(refill[:take])
            remaining -= take
        chosen_set = set(chosen)
        unseen = [sample_id for sample_id in unseen if sample_id not in chosen_set]
        seen_set = set(seen)
        seen.extend(sample_id for sample_id in chosen if sample_id not in seen_set)
        epoch_gold = list(gold_ids)
        rng.shuffle(epoch_gold)
        ordered = [{"id": sample_id, "label_source": "human"} for sample_id in epoch_gold]
        ordered += [
            {"id": sample_id, "label_source": "model_a+llm_review"}
            for sample_id in chosen
        ]
        rng.shuffle(ordered)
        epochs.append(
            {
                "epoch_index": epoch_index,
                "epoch_seed": seed + epoch_index,
                "gold_count": len(epoch_gold),
                "pseudo_count": len(chosen),
                "gold_ids": epoch_gold,
                "pseudo_ids": chosen,
                "ordered_ids": ordered,
                "replacement_used": replacement,
            }
        )
    return epochs, replacement


def sample_model_c_epochs(
    gold_ids: list[str],
    pseudo_ids: list[str],
    *,
    seed: int,
    pseudo_per_epoch: int,
) -> list[dict[str, Any]]:
    """Preserve Model C's unique epochs and final-epoch-only wrap behavior."""
    if len(gold_ids) != pseudo_per_epoch:
        raise ValueError("Gold count must equal pseudo_per_epoch")
    if len(pseudo_ids) < pseudo_per_epoch:
        raise ValueError("Model C pool must contain at least pseudo_per_epoch unique IDs")
    if len(set(gold_ids)) != len(gold_ids) or len(set(pseudo_ids)) != len(pseudo_ids):
        raise ValueError("Training pools contain duplicate IDs")
    unseen, used, epochs = sorted(pseudo_ids), [], []
    for epoch_index in range(math.ceil(len(pseudo_ids) / pseudo_per_epoch)):
        rng = random.Random(seed + epoch_index)
        candidates = list(unseen)
        rng.shuffle(candidates)
        chosen = candidates[:pseudo_per_epoch]
        missing = pseudo_per_epoch - len(chosen)
        if missing:
            refill = list(used)
            rng.shuffle(refill)
            chosen.extend(refill[:missing])
        chosen_set = set(chosen)
        unseen = [sample_id for sample_id in unseen if sample_id not in chosen_set]
        used_set = set(used)
        used.extend(sample_id for sample_id in chosen if sample_id not in used_set)
        epoch_gold = sorted(gold_ids)
        rng.shuffle(epoch_gold)
        ordered = [{"id": sample_id, "label_source": "human"} for sample_id in epoch_gold]
        ordered += [
            {"id": sample_id, "label_source": "model_a+llm_review"}
            for sample_id in chosen
        ]
        rng.shuffle(ordered)
        epochs.append(
            {
                "epoch_index": epoch_index,
                "epoch_seed": seed + epoch_index,
                "gold_count": len(epoch_gold),
                "pseudo_count": len(chosen),
                "gold_ids": epoch_gold,
                "pseudo_ids": chosen,
                "ordered_ids": ordered,
                "replacement_used": bool(missing),
            }
        )
    return epochs


def _content_hash(manifest: dict[str, Any]) -> str:
    payload = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return sha256_bytes(payload)


def _verify_phase3_artifact(root: Path, index: dict[str, dict[str, Any]], relative: str) -> str:
    if relative not in index:
        raise ValueError(f"Phase 3 manifest is missing {relative}")
    path, expected = root / relative, index[relative]
    actual = sha256_file(path)
    if actual != expected["sha256"] or path.stat().st_size != expected["bytes"]:
        raise ValueError(f"Frozen artifact mismatch: {relative}")
    return actual


def build_model_b_manifest(root: Path, config_path: Path, phase3_path: Path) -> dict[str, Any]:
    """Reconstruct the frozen deterministic Model B mixture manifest."""
    config, phase3 = load_json(config_path), load_json(phase3_path)
    if phase3.get("completion_status") != config["expected_phase3_completion_status"]:
        raise ValueError("Unapproved Phase 3 status")
    index = {artifact["path"].replace("\\", "/"): artifact for artifact in phase3["artifacts"]}
    paths = {
        "gold": "data/processed/vilexnorm_train.jsonl",
        "dev": "data/processed/vilexnorm_dev.jsonl",
        "pseudo": "data/processed/visolex_weak_labeled.jsonl",
    }
    checksums = {key: _verify_phase3_artifact(root, index, path) for key, path in paths.items()}
    gold, dev, pseudo = (read_jsonl(root / paths[key]) for key in ("gold", "dev", "pseudo"))
    validate_records(gold, dev, pseudo, config["prompt_version"])
    expected = (config["expected_gold_count"], config["expected_dev_count"], config["expected_weak_label_count"])
    if (len(gold), len(dev), len(pseudo)) != expected:
        raise ValueError(f"Unexpected counts: {(len(gold), len(dev), len(pseudo))} != {expected}")
    epochs, replacement = sample_model_b_epochs(
        [row["id"] for row in gold], [row["id"] for row in pseudo],
        seed=config["seed"], num_epochs=config["num_train_epochs"], pseudo_per_epoch=config["pseudo_per_epoch"],
    )
    usage = Counter(sample_id for epoch in epochs for sample_id in epoch["pseudo_ids"])
    if len(pseudo) >= config["pseudo_per_epoch"] and any(len(set(epoch["pseudo_ids"])) != len(epoch["pseudo_ids"]) for epoch in epochs):
        raise AssertionError("Duplicate pseudo in epoch")
    if len(usage) != len(pseudo):
        raise AssertionError("Pseudo pool coverage incomplete")
    manifest: dict[str, Any] = {
        "schema_version": 1, "phase": 4, "phase3_manifest_path": phase3_path.relative_to(root).as_posix(),
        "phase3_manifest_sha256": sha256_file(phase3_path), "completion_status": phase3["completion_status"],
        "input_paths": paths, "checksums": checksums, "gold_count": len(gold), "dev_count": len(dev),
        "weak_label_count": len(pseudo), "gold_pseudo_ratio": "1:1", "pseudo_per_epoch": config["pseudo_per_epoch"],
        "prompt_version": config["prompt_version"],
        "decision_distribution": dict(sorted(Counter(row["llm_decision"] for row in pseudo).items())),
        "source_distribution": dict(sorted(Counter(row["original_source"] for row in pseudo).items())),
        "replacement_used": replacement, "pseudo_union_count": len(usage),
        "pseudo_usage_distribution": {str(key): value for key, value in sorted(Counter(usage.values()).items())},
        "epochs": epochs,
    }
    manifest["manifest_content_sha256"] = _content_hash(manifest)
    return manifest


def build_model_c_manifest(root: Path, config_path: Path) -> dict[str, Any]:
    """Reconstruct the frozen deterministic Model C mixture manifest."""
    from visolexnorm.training.reports import checkpoint_inventory

    config = load_json(config_path)
    frozen_path = root / config["expanded_artifact_manifest_path"]
    frozen = load_json(frozen_path)
    if frozen.get("phase") != 8 or frozen.get("status") != "frozen":
        raise ValueError("Expanded weak-label pool is not frozen")
    paths = {"gold": config["gold_path"], "dev": config["dev_path"], "pseudo": config["expanded_weak_label_path"]}
    checksums = {key: sha256_file(root / relative) for key, relative in paths.items()}
    matches = [item for item in frozen.get("artifacts", []) if item.get("path") == paths["pseudo"]]
    if len(matches) != 1:
        raise ValueError(f"Frozen Phase 8 manifest is missing {paths['pseudo']}")
    if checksums["pseudo"] != matches[0]["sha256"]:
        raise ValueError("Expanded weak-label pool changed after freeze")
    gold, dev, pseudo = (read_jsonl(root / paths[key]) for key in ("gold", "dev", "pseudo"))
    validate_records(gold, dev, pseudo, config["prompt_version"])
    if (len(gold), len(dev)) != (config["expected_gold_count"], config["expected_dev_count"]):
        raise ValueError("Unexpected ViLexNorm Train/Dev count")
    _, inventory_sha = checkpoint_inventory(root / config["initial_checkpoint"])
    if inventory_sha != config["expected_initial_checkpoint_inventory_sha256"]:
        raise ValueError("Model A checkpoint inventory changed")
    epochs = sample_model_c_epochs([row["id"] for row in gold], [row["id"] for row in pseudo], seed=config["seed"], pseudo_per_epoch=config["pseudo_per_epoch"])
    usage = Counter(sample_id for epoch in epochs for sample_id in epoch["pseudo_ids"])
    if len(usage) != len(pseudo):
        raise AssertionError("Expanded pseudo pool coverage is incomplete")
    manifest: dict[str, Any] = {
        "schema_version": 1, "phase": 8, "completion_status": frozen["completion_status"],
        "expanded_artifact_manifest_path": config["expanded_artifact_manifest_path"],
        "expanded_artifact_manifest_sha256": sha256_file(frozen_path), "model_a_inventory_sha256": inventory_sha,
        "input_paths": paths, "checksums": checksums, "gold_count": len(gold), "dev_count": len(dev),
        "weak_label_count": len(pseudo), "gold_pseudo_ratio": "1:1", "pseudo_per_epoch": config["pseudo_per_epoch"],
        "num_train_epochs": len(epochs), "prompt_version": config["prompt_version"],
        "decision_distribution": dict(sorted(Counter(row["llm_decision"] for row in pseudo).items())),
        "source_distribution": dict(sorted(Counter(row["original_source"] for row in pseudo).items())),
        "replacement_used": any(epoch["replacement_used"] for epoch in epochs), "pseudo_union_count": len(usage),
        "pseudo_usage_distribution": {str(key): value for key, value in sorted(Counter(usage.values()).items())},
        "epochs": epochs,
    }
    manifest["manifest_content_sha256"] = _content_hash(manifest)
    return manifest


def validate_model_b_manifest(manifest: dict[str, Any], config: dict[str, Any]) -> None:
    """Validate Model B's frozen count, membership, and coverage contract."""
    epochs = manifest.get("epochs", [])
    if (manifest.get("gold_count"), manifest.get("dev_count"), manifest.get("weak_label_count")) != (config["expected_gold_count"], config["expected_dev_count"], config["expected_weak_label_count"]):
        raise ValueError("Mixture manifest counts do not match the frozen contract")
    if manifest.get("completion_status") != config["expected_phase3_completion_status"] or len(epochs) != config["num_train_epochs"]:
        raise ValueError("Mixture manifest status or epoch count is invalid")
    covered: set[str] = set()
    for index, epoch in enumerate(epochs):
        gold_ids, pseudo_ids = epoch.get("gold_ids", []), epoch.get("pseudo_ids", [])
        if epoch.get("epoch_seed") != config["seed"] + index or len(gold_ids) != config["gold_per_epoch"] or len(pseudo_ids) != config["pseudo_per_epoch"]:
            raise ValueError(f"Invalid membership contract in epoch {index}")
        if len(set(gold_ids)) != len(gold_ids) or (not epoch.get("replacement_used") and len(set(pseudo_ids)) != len(pseudo_ids)):
            raise ValueError(f"Duplicate membership in epoch {index}")
        expected = {(sample_id, "human") for sample_id in gold_ids} | {(sample_id, "model_a+llm_review") for sample_id in pseudo_ids}
        actual = {(row.get("id"), row.get("label_source")) for row in epoch.get("ordered_ids", [])}
        if actual != expected or len(epoch.get("ordered_ids", [])) != len(gold_ids) + len(pseudo_ids):
            raise ValueError(f"ordered_ids mismatch in epoch {index}")
        covered.update(pseudo_ids)
    if len(covered) != config["expected_weak_label_count"]:
        raise ValueError("Mixture manifest does not cover the frozen pseudo pool")


def validate_model_c_manifest(manifest: dict[str, Any], config: dict[str, Any]) -> None:
    """Validate Model C's complete pool coverage and final wrap contract."""
    epochs = manifest.get("epochs", [])
    if manifest.get("phase") != 8 or not epochs or len(epochs) != manifest.get("num_train_epochs"):
        raise ValueError("Model C mixture phase or epoch count is invalid")
    if manifest.get("model_a_inventory_sha256") != config["expected_initial_checkpoint_inventory_sha256"]:
        raise ValueError("Model C mixture does not reference the frozen Model A inventory")
    if (manifest.get("gold_count"), manifest.get("dev_count")) != (config["expected_gold_count"], config["expected_dev_count"]):
        raise ValueError("Model C mixture Train/Dev counts are invalid")
    covered: set[str] = set()
    for index, epoch in enumerate(epochs):
        gold_ids, pseudo_ids = epoch.get("gold_ids", []), epoch.get("pseudo_ids", [])
        if epoch.get("epoch_seed") != config["seed"] + index:
            raise ValueError(f"Invalid epoch seed at {index}")
        if len(gold_ids) != config["gold_per_epoch"] or len(pseudo_ids) != config["pseudo_per_epoch"]:
            raise ValueError(f"Invalid 1:1 membership at epoch {index}")
        if len(set(gold_ids)) != len(gold_ids) or len(set(pseudo_ids)) != len(pseudo_ids):
            raise ValueError(f"Duplicate membership at epoch {index}")
        if epoch.get("replacement_used") != (index == len(epochs) - 1 and len(covered) + len(pseudo_ids) > manifest["weak_label_count"]):
            raise ValueError(f"Invalid final-epoch wrap flag at epoch {index}")
        expected = {(sample_id, "human") for sample_id in gold_ids} | {(sample_id, "model_a+llm_review") for sample_id in pseudo_ids}
        actual = {(row.get("id"), row.get("label_source")) for row in epoch.get("ordered_ids", [])}
        if actual != expected or len(epoch.get("ordered_ids", [])) != len(gold_ids) + len(pseudo_ids):
            raise ValueError(f"ordered_ids mismatch in epoch {index}")
        covered.update(pseudo_ids)
    if len(covered) != manifest.get("weak_label_count") or manifest.get("pseudo_union_count") != len(covered):
        raise ValueError("Model C mixture does not cover the frozen pseudo pool")