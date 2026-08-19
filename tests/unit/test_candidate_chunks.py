from __future__ import annotations

from pathlib import Path

from scripts.generate_candidates import load_completed_chunk
from scripts.phase3_utils import atomic_write_jsonl


def candidate(sample_id: str, config_hash: str) -> dict:
    return {
        "id": sample_id, "dataset": "ViSoLex", "original_source": "ViHSD",
        "input_text": "mik ko bt", "candidate_text": "mình không biết",
        "model_a_confidence": -0.2, "candidate_checkpoint": "model_a",
        "generation_config_hash": config_hash, "sequence_token_count": 4,
        "generation_status": "generated_text",
    }


def source(sample_id: str) -> dict:
    return {"id": sample_id, "dataset": "ViSoLex", "original_source": "ViHSD", "input_text": "mik ko bt"}


def test_completed_chunk_is_reusable(tmp_path: Path) -> None:
    config_hash = "a" * 64
    path = tmp_path / "chunk.jsonl"
    atomic_write_jsonl([candidate("visolex_1", config_hash)], path)
    assert load_completed_chunk(path, [source("visolex_1")], config_hash) is not None


def test_wrong_config_hash_invalidates_chunk(tmp_path: Path) -> None:
    path = tmp_path / "chunk.jsonl"
    atomic_write_jsonl([candidate("visolex_1", "a" * 64)], path)
    assert load_completed_chunk(path, [source("visolex_1")], "b" * 64) is None


def test_empty_decoded_candidate_is_reusable_when_explicitly_audited(tmp_path: Path) -> None:
    config_hash = "a" * 64
    path = tmp_path / "chunk.jsonl"
    row = candidate("visolex_icon", config_hash)
    row["input_text"] = "🥰🥰🥰"
    row["candidate_text"] = ""
    row["generation_status"] = "empty_after_special_token_decode"
    expected = source("visolex_icon")
    expected["input_text"] = "🥰🥰🥰"
    atomic_write_jsonl([row], path)
    assert load_completed_chunk(path, [expected], config_hash) is not None