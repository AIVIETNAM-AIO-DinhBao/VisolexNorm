"""Explicit training policies for gold-only, Model B, and Model C workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from visolexnorm.training.mixtures import validate_model_b_manifest, validate_model_c_manifest
from visolexnorm.training.reports import reject_prohibited_inputs


ManifestValidator = Callable[[dict[str, Any], dict[str, Any]], None]


@dataclass(frozen=True)
class GoldTrainingStrategy:
    model_name: str = "model_a"
    phase: int = 2


@dataclass(frozen=True)
class MixtureTrainingStrategy:
    model_name: str
    phase: int
    pseudo_filename: str
    manifest_validator: ManifestValidator

    def validate_inputs(self, options: Any, config: dict[str, Any]) -> None:
        """Apply optional model-specific input restrictions before training."""


@dataclass(frozen=True)
class ModelBTrainingStrategy(MixtureTrainingStrategy):
    model_name: str = "model_b"
    phase: int = 4
    pseudo_filename: str = "visolex_weak_labeled.jsonl"
    manifest_validator: ManifestValidator = validate_model_b_manifest


@dataclass(frozen=True)
class ModelCTrainingStrategy(MixtureTrainingStrategy):
    model_name: str = "model_c"
    phase: int = 8
    pseudo_filename: str = "visolex_weak_labeled_expanded.jsonl"
    manifest_validator: ManifestValidator = validate_model_c_manifest

    def validate_inputs(self, options: Any, config: dict[str, Any]) -> None:
        reject_prohibited_inputs(options, config)