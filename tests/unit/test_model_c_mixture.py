from collections import Counter

import pytest

from scripts.build_model_c_mixture import sample_model_c_epochs
from scripts.train_model_c import assert_dev_only_report, reject_prohibited_inputs, validate_model_c_manifest
from argparse import Namespace
from pathlib import Path


def test_model_c_rotation_is_deterministic_balanced_and_complete() -> None:
    gold = [f"g{i}" for i in range(4)]
    pseudo = [f"p{i}" for i in range(10)]
    first = sample_model_c_epochs(gold, pseudo, seed=2026, pseudo_per_epoch=4)
    second = sample_model_c_epochs(gold, pseudo, seed=2026, pseudo_per_epoch=4)
    assert first == second
    assert [epoch["epoch_seed"] for epoch in first] == [2026, 2027, 2028]
    assert all(epoch["gold_count"] == epoch["pseudo_count"] == 4 for epoch in first)
    assert all(not epoch["replacement_used"] for epoch in first[:-1])
    assert first[-1]["replacement_used"]
    usage = Counter(sample_id for epoch in first for sample_id in epoch["pseudo_ids"])
    assert len(usage) == 10 and Counter(usage.values()) == {1: 8, 2: 2}


def test_model_c_requires_one_full_unique_epoch() -> None:
    with pytest.raises(ValueError, match="at least pseudo_per_epoch"):
        sample_model_c_epochs(["g1", "g2"], ["p1"], seed=2026, pseudo_per_epoch=2)


def test_model_c_rejects_test_input_path() -> None:
    args = Namespace(
        model_a_checkpoint=Path("checkpoints/model_a"), data_dir=Path("data/processed"),
        mixture_manifest=Path("outputs/model_c/manifest.json"), config=Path("vilexnorm_test.jsonl"),
    )
    with pytest.raises(ValueError, match="prohibited"):
        reject_prohibited_inputs(args, {"prohibited_input_paths": ["vilexnorm_test.jsonl", "outputs/evaluation/"]})


def test_model_c_manifest_rejects_non_final_wrap() -> None:
    epochs = sample_model_c_epochs(["g1", "g2"], ["p1", "p2", "p3"], seed=2026, pseudo_per_epoch=2)
    manifest = {
        "phase": 8, "num_train_epochs": 2, "model_a_inventory_sha256": "a" * 64,
        "gold_count": 2, "dev_count": 1, "weak_label_count": 3,
        "pseudo_union_count": 3, "epochs": epochs,
    }
    config = {
        "expected_initial_checkpoint_inventory_sha256": "a" * 64,
        "expected_gold_count": 2, "expected_dev_count": 1,
        "seed": 2026, "gold_per_epoch": 2, "pseudo_per_epoch": 2,
    }
    validate_model_c_manifest(manifest, config)
    manifest["epochs"][0]["replacement_used"] = True
    with pytest.raises(ValueError, match="wrap flag"):
        validate_model_c_manifest(manifest, config)


def test_exit_report_rejects_test_results() -> None:
    report = {"evaluation_scope": "dev_only_exploratory", "test_inputs_loaded": False}
    assert_dev_only_report(report)
    report["dev_evaluation"] = {"test_f1": 0.9}
    with pytest.raises(ValueError, match="forbidden Test results"):
        assert_dev_only_report(report)