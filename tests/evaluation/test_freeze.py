import json
from argparse import Namespace
from pathlib import Path

import pytest

from visolexnorm.evaluation.freeze import build_manifest, verify_manifest


def _checkpoint(path: Path) -> None:
    path.mkdir()
    (path / "config.json").write_text("{}")
    (path / "model.safetensors").write_bytes(b"weights")
    (path / "sentencepiece.bpe.model").write_bytes(b"tokenizer")


def _args(tmp_path: Path) -> Namespace:
    model_a, model_b = tmp_path / "model_a", tmp_path / "model_b"
    _checkpoint(model_a); _checkpoint(model_b)
    test = tmp_path / "test.jsonl"
    test.write_text("\n".join(json.dumps({"id": f"test-{i}", "dataset": "ViLexNorm", "split": "test", "input_text": "ko", "target_text": "không"}) for i in range(2)) + "\n")
    config, metric, phase3, phase4, reference = (tmp_path / name for name in ("config.json", "metric.py", "phase3.json", "phase4.json", "reference.json"))
    config.write_text("{}")
    metric.write_text("# metric")
    phase3.write_text("{}")
    phase4.write_text("{}")
    reference.write_text("{}")
    return Namespace(model_a_checkpoint=model_a, model_b_checkpoint=model_b, test=test, generation_config=config, metric_code=metric, phase3_manifest=phase3, phase4_exit_report=phase4, metric_reference=reference, expected_test_count=2)


def test_manifest_verification_detects_tampering(tmp_path: Path) -> None:
    args = _args(tmp_path)
    manifest = build_manifest(args)
    paths = {"model_a_checkpoint": args.model_a_checkpoint, "model_b_checkpoint": args.model_b_checkpoint, "test": args.test, "generation_config": args.generation_config, "metric_code": args.metric_code, "phase3_manifest": args.phase3_manifest, "phase4_exit_report": args.phase4_exit_report}
    verify_manifest(manifest, paths)
    args.generation_config.write_text('{"changed": true}')
    with pytest.raises(ValueError, match="generation_config"):
        verify_manifest(manifest, paths)


def test_manifest_rejects_different_tokenizers(tmp_path: Path) -> None:
    args = _args(tmp_path)
    (args.model_b_checkpoint / "sentencepiece.bpe.model").write_bytes(b"different tokenizer")
    with pytest.raises(ValueError, match="tokenizer"):
        build_manifest(args)


def test_manifest_normalizes_text_line_endings_only(tmp_path: Path) -> None:
    args = _args(tmp_path)
    args.generation_config.write_bytes(b'{\r\n  "seed": 2026\r\n}\r\n')
    args.metric_code.write_bytes(b"def metric():\r\n    return 1\r\n")
    manifest = build_manifest(args)
    paths = {"model_a_checkpoint": args.model_a_checkpoint, "model_b_checkpoint": args.model_b_checkpoint, "test": args.test, "generation_config": args.generation_config, "metric_code": args.metric_code, "phase3_manifest": args.phase3_manifest, "phase4_exit_report": args.phase4_exit_report}
    args.generation_config.write_bytes(b'{\n  "seed": 2026\n}\n')
    args.metric_code.write_bytes(b"def metric():\n    return 1\n")
    verify_manifest(manifest, paths)