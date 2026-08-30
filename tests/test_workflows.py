"""Guards for package APIs and active workflow entry-point migration."""

from __future__ import annotations

import importlib
import inspect
import json
import re
import typing
from argparse import Namespace
from pathlib import Path

import pytest

import scripts.training as training_cli
import visolexnorm.training.gold as gold_training
from visolexnorm.training.strategies import ModelBTrainingStrategy
from visolexnorm.training.strategies import ModelCTrainingStrategy
from visolexnorm.training.trainer import run_mixture_training


ROOT = Path(__file__).parents[1]
REMOVED_ENTRY_POINTS = re.compile(
    r"scripts/(?:build_model_[bc]_mixture|train_model_[abc]|freeze_experiment|"
    r"generate_test_predictions|evaluate_predictions|build_error_analysis)\.py"
)
ACTIVE_DOCUMENTS = [
    ROOT / "README.md",
    ROOT / "specs/004-model-b-training/quickstart.md",
    ROOT / "specs/005-experiment-evaluation/quickstart.md",
    ROOT / "specs/008-expanded-visolex-training/quickstart.md",
]
ACTIVE_NOTEBOOKS = sorted((ROOT / "notebooks").glob("*.ipynb"))
DOMAIN_NAMES = ("data", "candidates", "reviews", "weak_labels", "training", "evaluation")
DIRECT_DOMAIN_COMMAND = re.compile(
    r"(?:python|!python)\s+scripts/(?:" + "|".join(DOMAIN_NAMES) + r")\.py"
)
PUBLIC_MODULES = (
    "visolexnorm.training.gold",
    "visolexnorm.training.mixtures",
    "visolexnorm.training.reports",
    "visolexnorm.training.strategies",
    "visolexnorm.training.trainer",
    "visolexnorm.evaluation.freeze",
    "visolexnorm.evaluation.predictions",
    "visolexnorm.evaluation.scoring",
    "visolexnorm.evaluation.errors",
)


def test_active_workflows_do_not_reference_removed_entry_points() -> None:
    stale: list[str] = []
    for path in ACTIVE_DOCUMENTS + ACTIVE_NOTEBOOKS:
        text = path.read_text(encoding="utf-8")
        stale.extend(f"{path.relative_to(ROOT)}: {match}" for match in REMOVED_ENTRY_POINTS.findall(text))
    assert not stale, "\n".join(stale)


def test_active_workflows_use_module_execution_without_bootstrap() -> None:
    stale: list[str] = []
    for path in ACTIVE_DOCUMENTS + ACTIVE_NOTEBOOKS:
        text = path.read_text(encoding="utf-8")
        if DIRECT_DOMAIN_COMMAND.search(text):
            stale.append(str(path.relative_to(ROOT)))
    assert not stale, "\n".join(stale)
    assert not (ROOT / "scripts/_bootstrap.py").exists()
    source = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "scripts").glob("*.py"))
    assert "sys.path.insert" not in source
    assert "ensure_project_root" not in source


def test_maintenance_command_map_covers_removed_entry_points() -> None:
    guide = (ROOT / "docs/maintenance.md").read_text(encoding="utf-8")
    historical_names = {
        "prepare_vilexnorm.py", "prepare_visolex.py", "check_data.py",
        "export_protected_hashes.py", "generate_candidates.py",
        "generate_model_a_candidates.py", "select_review_manifest.py",
        "select_remaining_review_manifest.py", "audit_candidate_full_run.py",
        "review_candidates.py", "review_with_gemini.py", "export_pilot_audit.py",
        "freeze_review_prompt.py", "build_weak_labels.py",
        "build_expanded_weak_labels.py", "audit_weak_labels.py",
        "build_model_b_mixture.py", "build_model_c_mixture.py",
        "train_model_a.py", "train_model_b.py", "train_model_c.py",
        "freeze_experiment.py", "generate_test_predictions.py",
        "evaluate_predictions.py", "build_error_analysis.py",
    }
    missing = sorted(name for name in historical_names if name not in guide)
    assert not missing, missing


def test_active_notebooks_are_valid_json_and_use_domain_clis() -> None:
    commands = "\n".join(path.read_text(encoding="utf-8") for path in ACTIVE_NOTEBOOKS)
    for path in ACTIVE_NOTEBOOKS:
        json.loads(path.read_text(encoding="utf-8"))
    assert "python -m scripts.training" in commands
    assert "'python', '-m', 'scripts.evaluation'" in commands
    assert "REPLACE_WITH_FIXED_PHASE5_COMMIT" not in commands


def test_public_workflow_type_hints_resolve() -> None:
    failures: list[str] = []
    for module_name in PUBLIC_MODULES:
        module = importlib.import_module(module_name)
        for name, value in inspect.getmembers(module, inspect.isfunction):
            if value.__module__ != module_name:
                continue
            try:
                typing.get_type_hints(value)
            except Exception as error:  # pragma: no cover - failure detail only
                failures.append(f"{module_name}.{name}: {error}")
    assert not failures, "\n".join(failures)


def test_mixture_trainer_requires_an_explicit_strategy() -> None:
    strategy = inspect.signature(run_mixture_training).parameters["strategy"]
    assert strategy.default is inspect.Parameter.empty
    assert "model_name" not in inspect.signature(run_mixture_training).parameters


def test_model_c_strategy_applies_leakage_guard() -> None:
    options = Namespace(
        model_a_checkpoint=Path("checkpoints/model_a"),
        data_dir=Path("data/processed"),
        mixture_manifest=Path("outputs/evaluation/model_c.json"),
        config=Path("configs/model_c_config.json"),
    )
    config = {"prohibited_input_paths": ["vilexnorm_test.jsonl", "outputs/evaluation/"]}
    with pytest.raises(ValueError, match="prohibited"):
        ModelCTrainingStrategy().validate_inputs(options, config)


@pytest.mark.parametrize(
    ("model", "strategy_type"),
    (("model_b", ModelBTrainingStrategy), ("model_c", ModelCTrainingStrategy)),
)
def test_training_cli_dispatches_mixture_strategy(
    monkeypatch: pytest.MonkeyPatch,
    model: str,
    strategy_type: type,
) -> None:
    captured: list[object] = []
    monkeypatch.setattr(
        training_cli,
        "run_mixture_training",
        lambda options, strategy: captured.append(strategy),
    )
    training_cli.train_mixture(Namespace(model=model))
    assert len(captured) == 1
    assert isinstance(captured[0], strategy_type)


def test_training_cli_dispatches_model_a_gold_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[object] = []
    monkeypatch.setattr(
        gold_training,
        "run_gold_training",
        lambda options: captured.append(options),
    )
    options = Namespace(model="model_a")
    training_cli.train_mixture(options)
    assert captured == [options]