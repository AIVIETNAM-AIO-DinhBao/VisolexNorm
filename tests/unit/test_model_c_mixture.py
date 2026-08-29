from collections import Counter
import json

import pytest

from visolexnorm.training.mixtures import sample_model_c_epochs, validate_model_c_manifest
from visolexnorm.training.reports import (
    assert_dev_only_report,
    build_exit_report,
    finalize_phase8,
    reject_prohibited_inputs,
)
from argparse import Namespace
from pathlib import Path
from visolexnorm.common.artifacts import sha256_file


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


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def create_model_c_artifact_tree(root: Path) -> None:
    output = root / "outputs/model_c"
    checkpoint = root / "checkpoints/model_c/model.safetensors"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_bytes(b"weights")
    write_json(output / "smoke_test.json", {
        "passed": True, "test_inputs_loaded": False, "checkpoint_reload": True,
    })
    write_json(output / "train_config.json", {
        "run_type": "full", "test_inputs_loaded": False, "source_revision": "revision",
        "checkpoint_inventory_sha256": "a" * 64, "best_dev_loss": 0.2,
    })
    write_json(output / "dev_metrics.json", {
        "dev_examples": 1, "best_dev_loss": 0.2, "exact_sentence_match": 0.5,
        "history": [{"epoch": 1, "dev_loss": 0.2}],
    })
    write_json(output / "training_mixture_manifest.json", {
        "epochs": [{"pseudo_ids": ["pseudo-1"]}], "pseudo_union_count": 1,
        "num_train_epochs": 1, "gold_count": 1, "pseudo_per_epoch": 1,
        "checksums": {"pseudo": "b" * 64},
    })
    (output / "dev_predictions.jsonl").write_text(
        json.dumps({"id": "vilexnorm_dev_000001", "prediction": "không"}) + "\n",
        encoding="utf-8",
    )
    write_json(root / "outputs/expanded_review/artifact_manifest.json", {
        "counts": {"phase3": 0, "phase8": 1, "expanded": 1},
    })
    write_json(root / "outputs/expanded_review/review_stats.json", {
        "manifest_review_count": 1, "valid_llm_review_count": 1,
        "provider_exclusion_count": 0, "reconciled_count": 1,
        "decision_counts": {"KEEP": 1},
    })
    write_json(root / "outputs/model_b/dev_metrics.json", {
        "best_dev_loss": 0.3, "exact_sentence_match": 0.4,
    })
    relative = checkpoint.relative_to(root).as_posix()
    write_json(output / "artifact_manifest.json", {
        "phase": 8, "model": "model_c", "run_type": "full",
        "artifacts": [{
            "path": relative, "bytes": checkpoint.stat().st_size,
            "sha256": sha256_file(checkpoint),
        }],
    })


def test_model_c_exit_report_build_and_finalize_use_common_hashing(tmp_path: Path) -> None:
    create_model_c_artifact_tree(tmp_path)
    report = build_exit_report(tmp_path)
    assert report["status"] == "completed"
    assert report["test_inputs_loaded"] is False
    assert report["acceptance"]["artifact_checksums_verified"] is True
    destination = finalize_phase8(tmp_path, tmp_path / "exit-report.json")
    assert json.loads(destination.read_text(encoding="utf-8"))["evaluation_scope"] == "dev_only_exploratory"