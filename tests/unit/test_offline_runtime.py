"""Offline Kaggle runtime integrity and packaging contracts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.build_kaggle_offline_runtime import DEFAULT_PLATFORMS, FORBIDDEN_WHEEL_PREFIXES, require_clean_commit
from visolexnorm.common.offline_runtime import verify_runtime


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _runtime(tmp_path: Path, *, python: str) -> Path:
    wheelhouse = tmp_path / "wheelhouse"
    source = tmp_path / "source"
    wheelhouse.mkdir()
    source.mkdir()
    wheel = wheelhouse / "example-1.0-py3-none-any.whl"
    bundle = source / "visolexnorm.bundle"
    requirements = tmp_path / "requirements-kaggle-offline.txt"
    wheel.write_bytes(b"wheel")
    bundle.write_bytes(b"bundle")
    requirements.write_text("example==1.0\n", encoding="utf-8")
    files = [
        {"path": path.relative_to(tmp_path).as_posix(), "bytes": path.stat().st_size, "sha256": _digest(path)}
        for path in (requirements, bundle, wheel)
    ]
    manifest = {
        "runtime": "visolexnorm_controlled_kaggle_offline",
        "target": {"os": "linux", "architecture": "x86_64", "python": python},
        "requirements_path": "requirements-kaggle-offline.txt",
        "files": files,
        "forbidden_wheel_prefixes": list(FORBIDDEN_WHEEL_PREFIXES),
    }
    (tmp_path / "offline-runtime-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path


def test_verify_offline_runtime_accepts_matching_manifest(tmp_path: Path) -> None:
    import sys

    runtime = _runtime(tmp_path, python=f"{sys.version_info.major}.{sys.version_info.minor}")
    assert verify_runtime(runtime)["runtime"] == "visolexnorm_controlled_kaggle_offline"


def test_verify_offline_runtime_rejects_tampering(tmp_path: Path) -> None:
    import sys

    runtime = _runtime(tmp_path, python=f"{sys.version_info.major}.{sys.version_info.minor}")
    (runtime / "wheelhouse/example-1.0-py3-none-any.whl").write_bytes(b"changed")
    with pytest.raises(RuntimeError, match="artifact mismatch"):
        verify_runtime(runtime)


def test_verify_offline_runtime_rejects_torch_wheel(tmp_path: Path) -> None:
    import sys

    runtime = _runtime(tmp_path, python=f"{sys.version_info.major}.{sys.version_info.minor}")
    torch_wheel = runtime / "wheelhouse/torch-2.0-cp312-manylinux2014_x86_64.whl"
    torch_wheel.write_bytes(b"forbidden")
    with pytest.raises(RuntimeError, match="forbidden"):
        verify_runtime(runtime)


def test_verify_offline_runtime_rejects_wrong_python_abi(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path, python="0.0")
    with pytest.raises(RuntimeError, match="requires Python"):
        verify_runtime(runtime)


def test_offline_runtime_builder_requires_git_checkout(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="Git checkout"):
        require_clean_commit(tmp_path)


def test_controlled_notebooks_have_no_network_bootstrap() -> None:
    root = Path(__file__).parents[2]
    for name in ("controlled_factorial_kaggle.ipynb", "c_max20_early_stopping_kaggle.ipynb"):
        text = (root / "notebooks" / name).read_text(encoding="utf-8")
        assert "github.com" not in text
        assert "REPOSITORY_URL" not in text
        assert "pip install -q -r requirements-kaggle.txt" not in text
        assert "source/visolexnorm.bundle" in text
        assert "install_runtime(RUNTIME" in text
        assert "PIP_NO_INDEX" in text


def test_factorial_notebook_is_non_interactive_save_version_workflow() -> None:
    root = Path(__file__).parents[2]
    text = (root / "notebooks" / "controlled_factorial_kaggle.ipynb").read_text(encoding="utf-8")
    assert "TARGET_SEED" not in text
    assert "TARGET_ARM" not in text
    assert "RESET_INTERRUPTED_RUN" not in text
    assert "TRAJECTORIES = [(seed, arm) for seed in (2026, 2126, 2226)" in text
    assert "for seed, arm in TRAJECTORIES" in text
    assert "cleanup-factorial-run" in text
    assert "Controlled factorial failed at {run_id}" in text


def test_offline_builder_covers_sentencepiece_and_legacy_manylinux_tags() -> None:
    assert DEFAULT_PLATFORMS == (
        "manylinux_2_27_x86_64",
        "manylinux2014_x86_64",
        "manylinux_2_17_x86_64",
    )