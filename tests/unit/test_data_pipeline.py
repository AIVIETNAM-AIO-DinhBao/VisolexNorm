from __future__ import annotations

from pathlib import Path

import pytest

from visolexnorm.common.io import read_jsonl, write_jsonl
from visolexnorm.data.preparation import SourceSpec, prepare_vilexnorm_split, prepare_visolex_corpus, protected_texts
from visolexnorm.data.validation import build_protected_hashes, validate_processed_data


def test_prepare_vilexnorm_split_preserves_order_ids_and_empty_filtering(tmp_path: Path) -> None:
    raw = tmp_path / "train.jsonl"
    write_jsonl([
        {"original": "  mik\tko  ", "normalized": " mình không "},
        {"original": "", "normalized": "ignored"},
        {"original": "ok", "normalized": ""},
        {"original": "2", "normalized": "hai"},
    ], raw)
    result = prepare_vilexnorm_split(raw, "train", "original", "normalized")
    assert result.skipped_empty == 2
    assert result.records == [
        {
            "id": "vilexnorm_train_000001", "dataset": "ViLexNorm", "split": "train",
            "input_text": "mik ko", "target_text": "mình không", "label_source": "human",
        },
        {
            "id": "vilexnorm_train_000002", "dataset": "ViLexNorm", "split": "train",
            "input_text": "2", "target_text": "hai", "label_source": "human",
        },
    ]


def test_prepare_visolex_preserves_first_source_and_filters_protected_text(tmp_path: Path) -> None:
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    write_jsonl([{"text": "  shared "}, {"text": "protected"}, {"text": "first"}, {"text": ""}], first)
    write_jsonl([{"text": "shared"}, {"text": "second"}], second)
    result = prepare_visolex_corpus(
        [SourceSpec("ViHSD", first, "text"), SourceSpec("UIT-VSMEC", second, "text")],
        {"protected"},
    )
    assert result.records == [
        {"id": "visolex_000001", "dataset": "ViSoLex", "original_source": "ViHSD", "input_text": "shared"},
        {"id": "visolex_000002", "dataset": "ViSoLex", "original_source": "ViHSD", "input_text": "first"},
        {"id": "visolex_000003", "dataset": "ViSoLex", "original_source": "UIT-VSMEC", "input_text": "second"},
    ]
    assert result.overlap_counts["ViHSD"] == 1
    assert result.duplicate_counts["UIT-VSMEC"] == 1


def test_validation_and_protected_hashes_cover_processed_artifacts(tmp_path: Path) -> None:
    for split, text in (("train", "train"), ("dev", "dev"), ("test", "test")):
        write_jsonl([{
            "id": f"vilexnorm_{split}_000001", "dataset": "ViLexNorm", "split": split,
            "input_text": text, "target_text": text, "label_source": "human",
        }], tmp_path / f"vilexnorm_{split}.jsonl")
    write_jsonl([{
        "id": "visolex_000001", "dataset": "ViSoLex", "original_source": "ViHSD", "input_text": "unlabeled",
    }], tmp_path / "visolex_unlabeled.jsonl")
    report = validate_processed_data(tmp_path)
    assert report.split_counts == {"train": 1, "dev": 1, "test": 1}
    assert report.source_counts["ViHSD"] == 1
    assert len(build_protected_hashes(tmp_path)) == 2
    assert protected_texts(tmp_path) == {"dev", "test"}
    write_jsonl([{
        "id": "visolex_000001", "dataset": "ViSoLex", "original_source": "ViHSD", "input_text": "dev",
    }], tmp_path / "visolex_unlabeled.jsonl")
    with pytest.raises(ValueError, match="overlaps"):
        validate_processed_data(tmp_path)