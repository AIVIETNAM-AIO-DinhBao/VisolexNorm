"""Validate the tracked artifact-retention and cleanup policy."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
INVENTORY = ROOT / "docs/artifact-retention.json"


def load_inventory() -> dict:
    return json.loads(INVENTORY.read_text(encoding="utf-8"))


def test_model_b_and_phase5_selection_artifacts_are_keep_local() -> None:
    inventory = load_inventory()
    by_path = {entry["path"]: entry for entry in inventory["artifacts"]}
    required = {
        "checkpoints/model_b",
        "outputs/evaluation/best_model.json",
        "outputs/evaluation/freeze_manifest.json",
        "outputs/evaluation/model_b_test_predictions.jsonl",
    }
    assert all(by_path[path]["retention"] == "keep-local" for path in required)
    assert inventory["policy"]["phase5_selected_model"] == "model_b"
    assert inventory["policy"]["model_b_required_for_phase6_t016"] is True
    assert by_path["checkpoints/model_c"]["retention"] == "keep-local"


def test_large_artifacts_are_not_marked_removed_without_external_storage() -> None:
    inventory = load_inventory()
    assert inventory["policy"]["external_destination_configured"] is False
    assert inventory["policy"]["large_artifacts_externalized"] is False
    assert inventory["cleanup_result"]["large_artifacts_removed"] is False
    pending = {
        entry["path"]
        for entry in inventory["artifacts"]
        if entry["retention"] == "externalize-pending"
    }
    assert {
        "checkpoints/model_a",
        "model_a_artifacts.zip",
        "model_c_artifacts.zip",
        "visolex_model_a_candidates.zip",
    } <= pending


def test_cleanup_result_is_complete_and_inventory_entries_are_well_formed() -> None:
    inventory = load_inventory()
    result = inventory["cleanup_result"]
    assert result["safe_cleanup_completed"] is True
    assert result["bytes_removed"] > 0
    assert result["externalization_status"] == "pending-no-destination-configured"
    for entry in inventory["artifacts"]:
        assert entry["path"]
        assert entry["bytes"] >= 0
        assert entry["retention"]
        if entry["kind"] == "file":
            assert len(entry["sha256"]) == 64