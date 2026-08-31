"""Lazy local BARTpho loader for the resolved application checkpoint."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any


TOKENIZER_FILES = (
    "config.json",
    "dict.txt",
    "generation_config.json",
    "sentencepiece.bpe.model",
    "tokenizer_config.json",
)


def _tokenizer_load_path(checkpoint: Path) -> Path:
    """Return a SentencePiece-safe tokenizer path on Windows Unicode workspaces.

    SentencePiece's Windows native loader can reject an otherwise valid model
    file when an ancestor path contains Vietnamese Unicode characters. Copying
    the small tokenizer assets to the ASCII Windows temp directory avoids this
    limitation without duplicating the multi-gigabyte model weights.
    """
    if os.name != "nt" or checkpoint.as_posix().isascii():
        return checkpoint
    digest = hashlib.sha256(str(checkpoint.resolve()).encode("utf-8")).hexdigest()
    cache = Path(tempfile.gettempdir()) / "visolexnorm-tokenizers" / digest
    cache.mkdir(parents=True, exist_ok=True)
    for name in TOKENIZER_FILES:
        source = checkpoint / name
        target = cache / name
        if not source.is_file():
            raise FileNotFoundError(f"Checkpoint tokenizer asset is missing: {source}")
        if not target.is_file() or target.stat().st_size != source.stat().st_size:
            shutil.copy2(source, target)
    return cache


@lru_cache(maxsize=1)
def load_tokenizer(checkpoint: str) -> Any:
    """Load the local tokenizer once for validation before model generation."""
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise RuntimeError(
            "Chưa cài đủ thư viện suy luận. Hãy cài requirements-inference.txt rồi thử lại."
        ) from error
    return AutoTokenizer.from_pretrained(_tokenizer_load_path(Path(checkpoint)), local_files_only=True)


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