"""Build the frozen deterministic training mixture for Model C."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from build_model_b_mixture import validate_records  # noqa: E402
from data_utils import read_jsonl  # noqa: E402
from phase3_utils import load_json, sha256_file  # noqa: E402
from train_model_b import checkpoint_inventory  # noqa: E402


def sample_model_c_epochs(
    gold_ids: list[str], pseudo_ids: list[str], *, seed: int, pseudo_per_epoch: int
) -> list[dict[str, Any]]:
    if len(gold_ids) != pseudo_per_epoch:
        raise ValueError("Gold count must equal pseudo_per_epoch")
    if len(pseudo_ids) < pseudo_per_epoch:
        raise ValueError("Model C pool must contain at least pseudo_per_epoch unique IDs")
    if len(set(gold_ids)) != len(gold_ids) or len(set(pseudo_ids)) != len(pseudo_ids):
        raise ValueError("Training pools contain duplicate IDs")
    unseen = sorted(pseudo_ids)
    used: list[str] = []
    epochs: list[dict[str, Any]] = []
    num_epochs = math.ceil(len(pseudo_ids) / pseudo_per_epoch)
    for epoch_index in range(num_epochs):
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
        ordered = ([{"id": sample_id, "label_source": "human"} for sample_id in epoch_gold]
                   + [{"id": sample_id, "label_source": "model_a+llm_review"} for sample_id in chosen])
        rng.shuffle(ordered)
        epochs.append({
            "epoch_index": epoch_index, "epoch_seed": seed + epoch_index,
            "gold_count": len(epoch_gold), "pseudo_count": len(chosen),
            "gold_ids": epoch_gold, "pseudo_ids": chosen, "ordered_ids": ordered,
            "replacement_used": bool(missing),
        })
    return epochs


def manifest_artifact(manifest: dict[str, Any], path: str) -> dict[str, Any]:
    matches = [entry for entry in manifest.get("artifacts", []) if entry.get("path") == path]
    if len(matches) != 1:
        raise ValueError(f"Frozen Phase 8 manifest is missing {path}")
    return matches[0]


def build_manifest(root: Path, config_path: Path) -> dict[str, Any]:
    config = load_json(config_path)
    frozen_path = root / config["expanded_artifact_manifest_path"]
    frozen = load_json(frozen_path)
    if frozen.get("phase") != 8 or frozen.get("status") != "frozen":
        raise ValueError("Expanded weak-label pool is not frozen")
    paths = {"gold": config["gold_path"], "dev": config["dev_path"], "pseudo": config["expanded_weak_label_path"]}
    checksums = {key: sha256_file(root / relative) for key, relative in paths.items()}
    pseudo_artifact = manifest_artifact(frozen, paths["pseudo"])
    if checksums["pseudo"] != pseudo_artifact["sha256"]:
        raise ValueError("Expanded weak-label pool changed after freeze")
    gold, dev, pseudo = (read_jsonl(root / paths[key]) for key in ("gold", "dev", "pseudo"))
    validate_records(gold, dev, pseudo, config["prompt_version"])
    if (len(gold), len(dev)) != (config["expected_gold_count"], config["expected_dev_count"]):
        raise ValueError("Unexpected ViLexNorm Train/Dev count")
    _, inventory_sha = checkpoint_inventory(root / config["initial_checkpoint"])
    if inventory_sha != config["expected_initial_checkpoint_inventory_sha256"]:
        raise ValueError("Model A checkpoint inventory changed")
    epochs = sample_model_c_epochs(
        [row["id"] for row in gold], [row["id"] for row in pseudo],
        seed=config["seed"], pseudo_per_epoch=config["pseudo_per_epoch"],
    )
    usage = Counter(sample_id for epoch in epochs for sample_id in epoch["pseudo_ids"])
    if len(usage) != len(pseudo):
        raise AssertionError("Expanded pseudo pool coverage is incomplete")
    manifest = {
        "schema_version": 1, "phase": 8,
        "completion_status": frozen["completion_status"],
        "expanded_artifact_manifest_path": config["expanded_artifact_manifest_path"],
        "expanded_artifact_manifest_sha256": sha256_file(frozen_path),
        "model_a_inventory_sha256": inventory_sha,
        "input_paths": paths, "checksums": checksums,
        "gold_count": len(gold), "dev_count": len(dev), "weak_label_count": len(pseudo),
        "gold_pseudo_ratio": "1:1", "pseudo_per_epoch": config["pseudo_per_epoch"],
        "num_train_epochs": len(epochs), "prompt_version": config["prompt_version"],
        "decision_distribution": dict(sorted(Counter(row["llm_decision"] for row in pseudo).items())),
        "source_distribution": dict(sorted(Counter(row["original_source"] for row in pseudo).items())),
        "replacement_used": any(epoch["replacement_used"] for epoch in epochs),
        "pseudo_union_count": len(usage),
        "pseudo_usage_distribution": {str(key): value for key, value in sorted(Counter(usage.values()).items())},
        "epochs": epochs,
    }
    payload = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    manifest["manifest_content_sha256"] = hashlib.sha256(payload).hexdigest()
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--config", type=Path, default=Path("configs/model_c_config.json"))
    parser.add_argument("--output", type=Path, default=Path("outputs/model_c/training_mixture_manifest.json"))
    args = parser.parse_args()
    root = args.repo_root.resolve()
    config = args.config if args.config.is_absolute() else root / args.config
    output = args.output if args.output.is_absolute() else root / args.output
    manifest = build_manifest(root, config)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "weak_label_count": manifest["weak_label_count"], "num_train_epochs": manifest["num_train_epochs"]}))


if __name__ == "__main__":
    main()