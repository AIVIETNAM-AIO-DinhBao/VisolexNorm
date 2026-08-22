"""Verify frozen Phase 3 inputs and build deterministic Model B epoch mixtures."""
from __future__ import annotations

import argparse, hashlib, json, random
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from .data_utils import read_jsonl
except ImportError:  # Direct execution: python scripts/build_model_b_mixture.py
    from data_utils import read_jsonl


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise ValueError(f"{path} must contain an object")
    return value


def verify_artifact(root: Path, index: dict[str, dict[str, Any]], relative: str) -> str:
    if relative not in index: raise ValueError(f"Phase 3 manifest is missing {relative}")
    path, expected = root / relative, index[relative]
    actual = sha256_file(path)
    if actual != expected["sha256"] or path.stat().st_size != expected["bytes"]:
        raise ValueError(f"Frozen artifact mismatch: {relative}")
    return actual


def validate_records(gold: list[dict], dev: list[dict], pseudo: list[dict], prompt: str) -> None:
    for rows, split in ((gold, "train"), (dev, "dev")):
        if len({r.get("id") for r in rows}) != len(rows): raise ValueError(f"Duplicate {split} ID")
        if any(r.get("dataset") != "ViLexNorm" or r.get("split") != split or r.get("label_source") != "human" or not r.get("input_text") or not r.get("target_text") for r in rows):
            raise ValueError(f"Invalid ViLexNorm {split} record")
    if {r["id"] for r in gold} & {r["id"] for r in dev}: raise ValueError("Train/Dev ID overlap")
    if len({r.get("id") for r in pseudo}) != len(pseudo): raise ValueError("Duplicate pseudo ID")
    if any(r.get("dataset") != "ViSoLex" or r.get("label_source") != "model_a+llm_review" or r.get("llm_decision") not in {"KEEP", "EDIT"} or r.get("accepted") is not True or r.get("prompt_version") != prompt or not r.get("target_text") for r in pseudo):
        raise ValueError("Invalid weak-label record")


def sample_epoch_ids(gold_ids: list[str], pseudo_ids: list[str], *, seed: int, num_epochs: int, pseudo_per_epoch: int) -> tuple[list[dict], bool]:
    if not gold_ids or not pseudo_ids: raise ValueError("Pools must be non-empty")
    gold_ids, pseudo_ids = sorted(gold_ids), sorted(pseudo_ids)
    unseen, seen, epochs = list(pseudo_ids), [], []
    replacement = len(pseudo_ids) < pseudo_per_epoch
    for epoch_index in range(num_epochs):
        rng = random.Random(seed + epoch_index)
        candidates = list(unseen); rng.shuffle(candidates)
        chosen = candidates[:pseudo_per_epoch]
        remaining = pseudo_per_epoch - len(chosen)
        if remaining and not replacement:
            reused = list(seen); rng.shuffle(reused); chosen.extend(reused[:remaining])
        while remaining and replacement:
            refill = list(pseudo_ids); rng.shuffle(refill)
            take = min(remaining, len(refill)); chosen.extend(refill[:take]); remaining -= take
        chosen_set = set(chosen)
        unseen = [x for x in unseen if x not in chosen_set]
        seen_set = set(seen); seen.extend(x for x in chosen if x not in seen_set)
        epoch_gold = list(gold_ids); rng.shuffle(epoch_gold)
        ordered = [{"id": x, "label_source": "human"} for x in epoch_gold] + [{"id": x, "label_source": "model_a+llm_review"} for x in chosen]
        rng.shuffle(ordered)
        epochs.append({"epoch_index": epoch_index, "epoch_seed": seed + epoch_index, "gold_count": len(epoch_gold), "pseudo_count": len(chosen), "gold_ids": epoch_gold, "pseudo_ids": chosen, "ordered_ids": ordered, "replacement_used": replacement})
    return epochs, replacement


def build_manifest(root: Path, config_path: Path, phase3_path: Path) -> dict[str, Any]:
    config, phase3 = load_json(config_path), load_json(phase3_path)
    if phase3.get("completion_status") != config["expected_phase3_completion_status"]: raise ValueError("Unapproved Phase 3 status")
    index = {a["path"].replace("\\", "/"): a for a in phase3["artifacts"]}
    paths = {"gold": "data/processed/vilexnorm_train.jsonl", "dev": "data/processed/vilexnorm_dev.jsonl", "pseudo": "data/processed/visolex_weak_labeled.jsonl"}
    checksums = {k: verify_artifact(root, index, v) for k, v in paths.items()}
    gold, dev, pseudo = (read_jsonl(root / paths[k]) for k in ("gold", "dev", "pseudo"))
    validate_records(gold, dev, pseudo, config["prompt_version"])
    got = len(gold), len(dev), len(pseudo)
    expected = config["expected_gold_count"], config["expected_dev_count"], config["expected_weak_label_count"]
    if got != expected: raise ValueError(f"Unexpected counts: {got} != {expected}")
    epochs, replacement = sample_epoch_ids([r["id"] for r in gold], [r["id"] for r in pseudo], seed=config["seed"], num_epochs=config["num_train_epochs"], pseudo_per_epoch=config["pseudo_per_epoch"])
    usage = Counter(x for e in epochs for x in e["pseudo_ids"])
    if len(pseudo) >= config["pseudo_per_epoch"] and any(len(set(e["pseudo_ids"])) != len(e["pseudo_ids"]) for e in epochs): raise AssertionError("Duplicate pseudo in epoch")
    if len(usage) != len(pseudo): raise AssertionError("Pseudo pool coverage incomplete")
    manifest = {"schema_version": 1, "phase": 4, "phase3_manifest_path": phase3_path.relative_to(root).as_posix(), "phase3_manifest_sha256": sha256_file(phase3_path), "completion_status": phase3["completion_status"], "input_paths": paths, "checksums": checksums, "gold_count": len(gold), "dev_count": len(dev), "weak_label_count": len(pseudo), "gold_pseudo_ratio": "1:1", "pseudo_per_epoch": config["pseudo_per_epoch"], "prompt_version": config["prompt_version"], "decision_distribution": dict(sorted(Counter(r["llm_decision"] for r in pseudo).items())), "source_distribution": dict(sorted(Counter(r["original_source"] for r in pseudo).items())), "replacement_used": replacement, "pseudo_union_count": len(usage), "pseudo_usage_distribution": {str(k): v for k, v in sorted(Counter(usage.values()).items())}, "epochs": epochs}
    payload = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    manifest["manifest_content_sha256"] = hashlib.sha256(payload).hexdigest()
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--repo-root", type=Path, default=Path(".")); parser.add_argument("--config", type=Path, default=Path("configs/model_b_config.json")); parser.add_argument("--phase3-manifest", type=Path, default=Path("outputs/phase3_manifest.json")); parser.add_argument("--output", type=Path, default=Path("outputs/model_b/training_mixture_manifest.json")); args = parser.parse_args()
    root = args.repo_root.resolve(); resolve = lambda p: p if p.is_absolute() else root / p
    manifest = build_manifest(root, resolve(args.config), resolve(args.phase3_manifest)); output = resolve(args.output); output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "pseudo_union_count": manifest["pseudo_union_count"]}))


if __name__ == "__main__": main()