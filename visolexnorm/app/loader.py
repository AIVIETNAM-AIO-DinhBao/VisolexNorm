"""Lazy local BARTpho loader for the resolved application checkpoint."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=2)
def load_model(checkpoint: str) -> tuple[Any, Any]:
    """Load tokenizer and model once per verified checkpoint path."""
    try:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    except ImportError as error:
        raise RuntimeError(
            "Install transformers, torch, sentencepiece, and safetensors before local inference."
        ) from error
    path = Path(checkpoint)
    return AutoTokenizer.from_pretrained(path), AutoModelForSeq2SeqLM.from_pretrained(path)