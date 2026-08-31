"""Lazy local BARTpho loader for the resolved application checkpoint."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def load_tokenizer(checkpoint: str) -> Any:
    """Load the local tokenizer once for validation before model generation."""
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError(
            "Chưa cài đủ thư viện suy luận. Hãy cài requirements-inference.txt rồi thử lại."
        ) from error
    return AutoTokenizer.from_pretrained(Path(checkpoint), local_files_only=True)


@lru_cache(maxsize=1)
def load_model(checkpoint: str) -> Any:
    """Load one local model and retain only the active checkpoint.

    Keeping a single entry is intentional: Model B and Model C are both large
    CPU checkpoints, and the rollback model must not remain in memory after a
    successful Model C load.
    """
    try:
        from transformers import AutoModelForSeq2SeqLM
    except ImportError as error:
        raise RuntimeError(
            "Chưa cài đủ thư viện suy luận. Hãy cài requirements-inference.txt rồi thử lại."
        ) from error
    model = AutoModelForSeq2SeqLM.from_pretrained(Path(checkpoint), local_files_only=True)
    model.eval()
    return model


def clear_model_cache() -> None:
    """Release cached tokenizer/model references, primarily for tests and shutdown."""
    load_tokenizer.cache_clear()
    load_model.cache_clear()