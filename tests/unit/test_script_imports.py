from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[2]
SCRIPTS = sorted(
    path.stem for path in (ROOT / "scripts").glob("*.py")
    if path.stem not in {"__init__", "_bootstrap"}
)
CLI_SCRIPTS = [name for name in SCRIPTS if name != "evaluation_metrics"]


def run_python(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(
        [sys.executable, *arguments], cwd=ROOT, env=environment,
        capture_output=True, text=True, encoding="utf-8",
    )


def test_all_script_modules_import_in_isolated_processes() -> None:
    failures = []
    for name in SCRIPTS:
        result = run_python("-c", f"import scripts.{name}")
        if result.returncode:
            failures.append(f"{name}: {result.stderr}")
    assert not failures, "\n".join(failures)


def test_all_direct_cli_entry_points_reach_help() -> None:
    failures = []
    for name in CLI_SCRIPTS:
        result = run_python(str(ROOT / "scripts" / f"{name}.py"), "--help")
        if result.returncode:
            failures.append(f"{name}: {result.stderr}")
    assert not failures, "\n".join(failures)


def test_review_cache_has_one_canonical_module_identity() -> None:
    import visolexnorm.review.cache as review_cache
    import visolexnorm.review.pipeline as review_pipeline

    assert "review_cache" not in sys.modules
    assert review_pipeline.ReviewCache is review_cache.ReviewCache


def test_training_cli_has_package_backed_subcommands() -> None:
    for command in ("build-mixture", "train", "finalize"):
        result = run_python(str(ROOT / "scripts" / "training.py"), command, "--help")
        assert result.returncode == 0, result.stderr


def test_evaluation_cli_has_package_backed_subcommands() -> None:
    for command in ("freeze", "verify-freeze", "generate", "score", "analyze-errors"):
        result = run_python(str(ROOT / "scripts" / "evaluation.py"), command, "--help")
        assert result.returncode == 0, result.stderr


def test_model_specific_cli_restrictions_fail_before_runtime_dependencies() -> None:
    invalid_finalize = run_python(
        str(ROOT / "scripts" / "training.py"),
        "finalize",
        "--model",
        "model_a",
    )
    invalid_generation = run_python(
        str(ROOT / "scripts" / "evaluation.py"),
        "generate",
        "--model",
        "model_c",
    )
    assert invalid_finalize.returncode == 2
    assert "invalid choice" in invalid_finalize.stderr
    assert invalid_generation.returncode == 2
    assert "invalid choice" in invalid_generation.stderr