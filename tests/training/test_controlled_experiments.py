"""Contracts for the Dev-only controlled factorial experiment."""
from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path

import pytest

from visolexnorm.training.controlled import (
    _require_clean_source_revision,
    freeze_protocol,
    sample_balanced_epochs,
    sample_factorial_epochs,
    summarize_factorial,
    validate_controlled_manifest,
)


def test_factorial_sampler_is_deterministic_nested_and_balanced() -> None:
    gold = [f"g{i}" for i in range(4)]
    initial = [f"p{i}" for i in range(10)]
    expanded = initial + [f"x{i}" for i in range(10)]
    first_small, first_large = sample_factorial_epochs(gold, initial, expanded, seed=2026, num_epochs=5, pseudo_per_epoch=4)
    second_small, second_large = sample_factorial_epochs(gold, initial, expanded, seed=2026, num_epochs=5, pseudo_per_epoch=4)
    assert (first_small, first_large) == (second_small, second_large)
    assert all(len(set(epoch["pseudo_ids"])) == 4 for epoch in first_small + first_large)
    small_usage = Counter(item for epoch in first_small for item in epoch["pseudo_ids"])
    large_usage = Counter(item for epoch in first_large for item in epoch["pseudo_ids"])
    assert len(small_usage) == 10
    assert len(large_usage) == 20
    assert max(small_usage.values()) - min(small_usage.values()) <= 1
    assert max(large_usage.values()) - min(large_usage.values()) <= 1
    for small, large in zip(first_small, first_large):
        fresh_initial = {item for item in small["pseudo_ids"] if sum(item in prior["pseudo_ids"] for prior in first_small[:small["epoch_index"]]) == 0}
        assert fresh_initial.issubset(set(large["pseudo_ids"]))


def test_factorial_sampler_rejects_non_nested_pools() -> None:
    with pytest.raises(ValueError, match="nested"):
        sample_factorial_epochs(["g1", "g2"], ["p1", "p2"], ["p1", "x1"], seed=2026, num_epochs=1, pseudo_per_epoch=2)


def test_cmax_sampler_balances_exposure_without_within_epoch_duplicates() -> None:
    epochs = sample_balanced_epochs(["g1", "g2", "g3"], [f"p{i}" for i in range(8)], seed=2026, num_epochs=7, pseudo_per_epoch=3)
    usage = Counter(item for epoch in epochs for item in epoch["pseudo_ids"])
    assert all(len(set(epoch["pseudo_ids"])) == 3 for epoch in epochs)
    assert max(usage.values()) - min(usage.values()) <= 1


def _manifest() -> dict:
    epochs = []
    for index in range(2):
        gold = ["g1", "g2"]
        pseudo = [f"p{index * 2 + 1}", f"p{index * 2 + 2}"]
        ordered = [{"id": item, "label_source": "human"} for item in gold] + [{"id": item, "label_source": "model_a+llm_review"} for item in pseudo]
        epochs.append({"epoch_index": index, "epoch_seed": 2026 + index, "gold_ids": gold, "pseudo_ids": pseudo, "ordered_ids": ordered})
    return {"experiment": "controlled_factorial_2x2", "seed": 2026, "pseudo_per_epoch": 2, "num_train_epochs": 2, "epochs": epochs, "test_inputs_loaded": False}


def test_controlled_manifest_validation_rejects_test_flag_and_order_tampering() -> None:
    config = {"seeds": [2026], "pseudo_per_epoch": 2}
    manifest = _manifest()
    validate_controlled_manifest(manifest, config)
    manifest["test_inputs_loaded"] = True
    with pytest.raises(ValueError, match="Dev-only"):
        validate_controlled_manifest(manifest, config)
    manifest["test_inputs_loaded"] = False
    manifest["epochs"][0]["ordered_ids"].pop()
    with pytest.raises(ValueError, match="ordering"):
        validate_controlled_manifest(manifest, config)


def _prediction(value: str) -> str:
    return json.dumps({"id": "dev-1", "input_text": "ko", "target_text": "không", "prediction": value}, ensure_ascii=False) + "\n"


def test_factorial_summary_is_dev_only_and_computes_interaction(tmp_path: Path) -> None:
    for seed in (2026, 2126):
        for arm, outputs in (("small", {3: "không", 8: "sai"}), ("expanded", {3: "sai", 8: "không"})):
            for horizon, prediction in outputs.items():
                path = tmp_path / f"seed_{seed}" / arm / f"horizon_{horizon}" / "dev_predictions.jsonl"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(_prediction(prediction), encoding="utf-8")
    result = summarize_factorial(tmp_path, tmp_path / "summary.json")
    assert result["seeds"] == 2
    assert result["test_metrics_used"] is False
    assert "interaction" in result["effects"]["f1"]


def test_cmax_manifest_requires_frozen_dev_loss_monitor() -> None:
    config = json.loads((Path(__file__).parents[2] / "configs/c_max20_early_stopping_config.json").read_text(encoding="utf-8"))
    assert config["monitor"] == "dev_loss"
    assert config["min_epochs"] == 8
    assert config["patience"] == 4


def test_protocol_revision_guard_rejects_non_git_directory(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="Git checkout"):
        _require_clean_source_revision(tmp_path)


def test_freeze_protocol_separates_git_source_and_data_roots(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    data_root = tmp_path / "data"
    source_root.mkdir()
    data_root.mkdir()
    (source_root / "README.md").write_text("committed source\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(source_root), "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(source_root), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(source_root), "config", "user.name", "Test User"], check=True)
    subprocess.run(["git", "-C", str(source_root), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(source_root), "commit", "-m", "test source"], check=True, capture_output=True)

    checkpoint = data_root / "checkpoints" / "model_a"
    checkpoint.mkdir(parents=True)
    (checkpoint / "config.json").write_text("{}\n", encoding="utf-8")
    (checkpoint / "model.safetensors").write_bytes(b"weights")
    (checkpoint / "tokenizer.json").write_text("{}\n", encoding="utf-8")
    input_paths = {
        "gold": "gold.jsonl",
        "dev": "dev.jsonl",
        "initial": "initial.jsonl",
        "expanded": "expanded.jsonl",
    }
    for name in input_paths.values():
        (data_root / name).write_text(name + "\n", encoding="utf-8")
    config = {
        "initial_checkpoint": "checkpoints/model_a",
        "input_paths": input_paths,
        "expected_initial_pool_count": 1,
        "expected_expanded_pool_count": 1,
        "seeds": [2026],
        "horizons": [3, 8],
        "max_epochs": 8,
        "pseudo_per_epoch": 1,
        "warmup_ratio": 0.1,
    }
    config_path = source_root / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    cmax_config_path = source_root / "cmax.json"
    cmax_config_path.write_text(json.dumps({
        "max_epochs": 20,
        "min_epochs": 8,
        "patience": 4,
        "min_delta": 0.0001,
        "monitor": "dev_loss",
    }), encoding="utf-8")
    subprocess.run(["git", "-C", str(source_root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(source_root), "commit", "-m", "test configs"], check=True, capture_output=True)

    protocol_path = tmp_path / "protocol.json"
    freeze_protocol(source_root, data_root, config_path, cmax_config_path, protocol_path)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    revision = subprocess.check_output(["git", "-C", str(source_root), "rev-parse", "HEAD"], text=True).strip()

    assert protocol["source_revision"] == revision
    assert protocol["input_checksums"]["gold"]
    assert protocol["model_a_inventory_sha256"]


def test_terminal_metric_name_is_distinct_from_selected_metric_name() -> None:
    selected = Path("horizon_3/dev_predictions.jsonl").with_name("dev_metrics.json")
    terminal = Path("horizon_3/terminal_dev_predictions.jsonl").with_name("terminal_dev_metrics.json")
    assert selected != terminal