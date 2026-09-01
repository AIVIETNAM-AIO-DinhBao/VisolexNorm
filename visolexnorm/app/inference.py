"""Offline command-line inference using the promoted Model C checkpoint."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from visolexnorm.app.loader import load_model, load_tokenizer
from visolexnorm.app.selection import resolve_checkpoint, selection_sha256


class InputValidationError(ValueError):
    """Raised when text cannot be sent safely to the normalizer."""


@dataclass(frozen=True)
class InferenceRuntime:
    """The verified checkpoint and its lazily loaded local model resources."""

    config: dict[str, Any]
    checkpoint: Path
    model_name: str
    tokenizer: Any


def _load_config(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Inference config must be a JSON object")
    return value


@lru_cache(maxsize=1)
def _load_runtime(config_path: str, root: str) -> InferenceRuntime:
    """Resolve and load a single verified runtime once for this process."""
    root_path = Path(root)
    config = _load_config(Path(config_path))
    resolved = resolve_checkpoint(root_path / config["selection_path"], root_path)
    tokenizer = load_tokenizer(str(resolved.checkpoint))
    return InferenceRuntime(config, resolved.checkpoint, resolved.model, tokenizer)


def clear_runtime_cache() -> None:
    """Clear the verified runtime cache, primarily for tests and shutdown."""
    _load_runtime.cache_clear()


def normalize(text: str, *, config_path: Path = Path("configs/app_inference_config.json"), root: Path = Path(".")) -> str:
    """Normalize one non-empty sentence with the verified selected checkpoint."""
    if not isinstance(text, str):
        raise InputValidationError("Vui lòng nhập văn bản cần chuẩn hóa.")
    value = text.strip()
    if not value:
        raise InputValidationError("Vui lòng nhập văn bản cần chuẩn hóa.")
    runtime = _load_runtime(str(config_path), str(root))
    token_count = len(runtime.tokenizer(value, add_special_tokens=True)["input_ids"])
    if token_count > int(runtime.config["max_source_length"]):
        raise InputValidationError("Văn bản vượt quá giới hạn 128 token.")
    try:
        import torch
    except ImportError as error:
        raise RuntimeError(
            "Chưa cài đủ thư viện suy luận. Hãy cài requirements-inference.txt rồi thử lại."
        ) from error
    with torch.inference_mode():
        generated = load_model(str(runtime.checkpoint)).generate(
            **runtime.tokenizer(value, return_tensors="pt"),
            num_beams=int(runtime.config["num_beams"]),
            max_length=int(runtime.config["max_length"]),
        )
    normalized = runtime.tokenizer.batch_decode(generated, skip_special_tokens=True)[0].strip()
    if not normalized:
        raise RuntimeError("Mô hình không tạo được kết quả chuẩn hóa. Vui lòng thử lại.")
    return normalized


def smoke_report(config_path: Path = Path("configs/app_inference_config.json"), root: Path = Path(".")) -> dict[str, Any]:
    """Verify application selection and checkpoint resolution before real inference."""
    config = _load_config(config_path)
    resolved = resolve_checkpoint(root / config["selection_path"], root)
    return {
        "schema_version": 1,
        "phase": 10,
        "passed": True,
        "selected_model": resolved.model,
        "fallback_model": resolved.selection.get("fallback_model", resolved.selection.get("rollback_model")),
        "fallback_applied": resolved.fallback_applied,
        "fallback_reason": resolved.fallback_reason,
        "checkpoint_path": resolved.checkpoint.as_posix(),
        "selection_sha256": selection_sha256(resolved.selection),
        "runtime_model_loaded": False,
        "note": "Run normalize() after local inference dependencies are installed to perform a real model-load smoke test.",
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
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