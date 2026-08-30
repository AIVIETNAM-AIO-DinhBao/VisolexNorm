"""Offline command-line inference using the promoted Model C checkpoint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from visolexnorm.app.loader import load_model
from visolexnorm.app.selection import resolve_checkpoint, selection_sha256


def _load_config(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Inference config must be a JSON object")
    return value


def normalize(text: str, *, config_path: Path = Path("configs/app_inference_config.json"), root: Path = Path(".")) -> str:
    """Normalize one non-empty sentence with the verified selected checkpoint."""
    value = text.strip()
    if not value:
        raise ValueError("Vui lòng nhập văn bản cần chuẩn hóa.")
    config = _load_config(config_path)
    resolved = resolve_checkpoint(root / config["selection_path"], root)
    tokenizer, model = load_model(str(resolved.checkpoint))
    token_count = len(tokenizer(value, add_special_tokens=True)["input_ids"])
    if token_count > int(config["max_source_length"]):
        raise ValueError("Văn bản vượt quá giới hạn 128 token.")
    generated = model.generate(
        **tokenizer(value, return_tensors="pt"),
        num_beams=int(config["num_beams"]),
        max_new_tokens=int(config["max_new_tokens"]),
    )
    return tokenizer.batch_decode(generated, skip_special_tokens=True)[0].strip()


def smoke_report(config_path: Path = Path("configs/app_inference_config.json"), root: Path = Path(".")) -> dict[str, Any]:
    """Verify application selection and checkpoint resolution before real inference."""
    config = _load_config(config_path)
    resolved = resolve_checkpoint(root / config["selection_path"], root)
    return {
        "schema_version": 1,
        "phase": 10,
        "passed": True,
        "selected_model": resolved.model,
        "rollback_model": resolved.selection["rollback_model"],
        "fallback_applied": resolved.fallback_applied,
        "fallback_reason": resolved.fallback_reason,
        "checkpoint_path": resolved.checkpoint.as_posix(),
        "selection_sha256": selection_sha256(resolved.selection),
        "runtime_model_loaded": False,
        "note": "Run normalize() after local inference dependencies are installed to perform a real model-load smoke test.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text")
    parser.add_argument("--config", type=Path, default=Path("configs/app_inference_config.json"))
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if args.smoke:
        print(json.dumps(smoke_report(args.config), ensure_ascii=False, indent=2))
        return
    if args.text is None:
        parser.error("Pass --text or --smoke")
    try:
        print(normalize(args.text, config_path=args.config))
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()