"""Integration tests for the local inference path without loading BARTpho."""

from __future__ import annotations

import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from visolexnorm.app import inference
from visolexnorm.app.selection import ResolvedCheckpoint


class StubTokenizer:
    def __init__(self, token_count: int = 3, decoded: str = "mình không biết") -> None:
        self.token_count = token_count
        self.decoded = decoded

    def __call__(self, text: str, **kwargs: object) -> dict[str, list[int]]:
        del text
        if kwargs.get("add_special_tokens"):
            return {"input_ids": list(range(self.token_count))}
        return {"input_ids": [1, 2, 3]}

    def batch_decode(self, generated: object, **kwargs: object) -> list[str]:
        del generated, kwargs
        return [self.decoded]


class StubModel:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate(self, **kwargs: object) -> list[list[int]]:
        self.calls.append(kwargs)
        return [[1, 2, 3]]


@pytest.fixture(autouse=True)
def reset_runtime_cache() -> None:
    inference.clear_runtime_cache()
    yield
    inference.clear_runtime_cache()


def write_config(tmp_path: Path) -> Path:
    config = tmp_path / "config.json"
    config.write_text(
        '{"selection_path":"selection.json","max_source_length":128,"max_length":128,"num_beams":4}',
        encoding="utf-8",
    )
    return config


def stub_resolution(tmp_path: Path, model: str = "model_c") -> ResolvedCheckpoint:
    return ResolvedCheckpoint(
        model=model,
        checkpoint=tmp_path / "checkpoints" / model,
        fallback_applied=model == "model_b",
        fallback_reason="selected checkpoint inventory mismatch" if model == "model_b" else None,
        selection={"rollback_model": "model_b"},
    )


def install_torch_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(inference_mode=nullcontext))


def test_normalize_uses_cached_runtime_and_frozen_generation_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = write_config(tmp_path)
    tokenizer = StubTokenizer()
    model = StubModel()
    calls = {"resolve": 0, "tokenizer": 0, "model": 0}

    def resolve(*args: object) -> ResolvedCheckpoint:
        del args
        calls["resolve"] += 1
        return stub_resolution(tmp_path)

    def load_tokenizer(*args: object) -> StubTokenizer:
        del args
        calls["tokenizer"] += 1
        return tokenizer

    def load_model(*args: object) -> StubModel:
        del args
        calls["model"] += 1
        return model

    monkeypatch.setattr(inference, "resolve_checkpoint", resolve)
    monkeypatch.setattr(inference, "load_tokenizer", load_tokenizer)
    monkeypatch.setattr(inference, "load_model", load_model)
    install_torch_stub(monkeypatch)

    assert inference.normalize("  mik ko bt  ", config_path=config, root=tmp_path) == "mình không biết"
    assert inference.normalize("t cx ko bik", config_path=config, root=tmp_path) == "mình không biết"

    assert calls == {"resolve": 1, "tokenizer": 1, "model": 2}
    assert model.calls[0]["num_beams"] == 4
    assert model.calls[0]["max_length"] == 128


def test_normalize_rejects_empty_and_long_input_before_model_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = write_config(tmp_path)
    tokenizer = StubTokenizer(token_count=129)
    model_loads = 0

    monkeypatch.setattr(inference, "resolve_checkpoint", lambda *args: stub_resolution(tmp_path))
    monkeypatch.setattr(inference, "load_tokenizer", lambda *args: tokenizer)

    def load_model(*args: object) -> StubModel:
        nonlocal model_loads
        del args
        model_loads += 1
        return StubModel()

    monkeypatch.setattr(inference, "load_model", load_model)

    with pytest.raises(inference.InputValidationError, match="Vui lòng nhập"):
        inference.normalize("   ", config_path=config, root=tmp_path)
    with pytest.raises(inference.InputValidationError, match="128 token"):
        inference.normalize("mot cau rat dai", config_path=config, root=tmp_path)

    assert model_loads == 0


def test_normalize_uses_rollback_checkpoint_returned_by_resolver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = write_config(tmp_path)
    checkpoint_paths: list[str] = []
    monkeypatch.setattr(inference, "resolve_checkpoint", lambda *args: stub_resolution(tmp_path, "model_b"))
    monkeypatch.setattr(inference, "load_tokenizer", lambda checkpoint: checkpoint_paths.append(checkpoint) or StubTokenizer())
    monkeypatch.setattr(inference, "load_model", lambda checkpoint: checkpoint_paths.append(checkpoint) or StubModel())
    install_torch_stub(monkeypatch)

    assert inference.normalize("t cx ko bik", config_path=config, root=tmp_path) == "mình không biết"
    assert checkpoint_paths == [str(tmp_path / "checkpoints" / "model_b")] * 2


def test_normalize_rejects_empty_model_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = write_config(tmp_path)
    monkeypatch.setattr(inference, "resolve_checkpoint", lambda *args: stub_resolution(tmp_path))
    monkeypatch.setattr(inference, "load_tokenizer", lambda *args: StubTokenizer(decoded=" "))
    monkeypatch.setattr(inference, "load_model", lambda *args: StubModel())
    install_torch_stub(monkeypatch)

    with pytest.raises(RuntimeError, match="không tạo được kết quả"):
        inference.normalize("t cx ko bik", config_path=config, root=tmp_path)