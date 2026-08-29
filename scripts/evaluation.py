"""Unified Phase 5 freeze, generation, scoring, and error-analysis command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts._bootstrap import ensure_project_root
except ModuleNotFoundError:
    from _bootstrap import ensure_project_root

ensure_project_root()

from visolexnorm.evaluation.errors import write_error_analysis
from visolexnorm.evaluation.freeze import build_manifest, verify_manifest
from visolexnorm.evaluation.predictions import generate_predictions
from visolexnorm.evaluation.scoring import evaluate


def freeze_paths(args: argparse.Namespace) -> dict[str, Path]:
    return {name: getattr(args, name) for name in ("model_a_checkpoint", "model_b_checkpoint", "test", "generation_config", "metric_code", "phase3_manifest", "phase4_exit_report")}


def run_freeze(args: argparse.Namespace) -> None:
    if args.output.exists():
        raise FileExistsError(f"Frozen manifest already exists: {args.output}; use verify-freeze, never overwrite it")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(build_manifest(args), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"frozen": True, "manifest": str(args.output)}))


def run_verify(args: argparse.Namespace) -> None:
    verify_manifest(json.loads(args.manifest.read_text(encoding="utf-8")), freeze_paths(args))
    print(json.dumps({"verified": True, "manifest": str(args.manifest)}))


def run_score(args: argparse.Namespace) -> None:
    from scripts.evaluation_metrics import OFFICIAL_REFERENCE, evaluate_records

    result = evaluate(args, evaluate_records=evaluate_records, metric_reference=OFFICIAL_REFERENCE)
    print(json.dumps({"selected_model": result["best_model"]["selected_model"], "metrics": result["metrics"]["models"]}, ensure_ascii=False, indent=2))


def add_frozen_inputs(parser: argparse.ArgumentParser, *, required: bool = False) -> None:
    parser.add_argument("--model-a-checkpoint", type=Path, required=required, default=None if required else Path("checkpoints/model_a"))
    parser.add_argument("--model-b-checkpoint", type=Path, required=required, default=None if required else Path("checkpoints/model_b"))
    parser.add_argument("--test", type=Path, required=required, default=None if required else Path("data/processed/vilexnorm_test.jsonl"))
    parser.add_argument("--generation-config", type=Path, required=required, default=None if required else Path("configs/evaluation_generation_config.json"))
    parser.add_argument("--metric-code", type=Path, required=required, default=None if required else Path("scripts/evaluation_metrics.py"))
    parser.add_argument("--phase3-manifest", type=Path, required=required, default=None if required else Path("outputs/phase3_manifest.json"))
    parser.add_argument("--phase4-exit-report", type=Path, required=required, default=None if required else Path("outputs/model_b/phase4_exit_report.json"))


def add_freeze_inputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model-a-checkpoint", type=Path, required=True)
    parser.add_argument("--model-b-checkpoint", type=Path, required=True)
    parser.add_argument("--test", type=Path, default=Path("data/processed/vilexnorm_test.jsonl"))
    parser.add_argument("--generation-config", type=Path, default=Path("configs/evaluation_generation_config.json"))
    parser.add_argument("--metric-code", type=Path, default=Path("scripts/evaluation_metrics.py"))
    parser.add_argument("--phase3-manifest", type=Path, default=Path("outputs/phase3_manifest.json"))
    parser.add_argument("--phase4-exit-report", type=Path, default=Path("outputs/model_b/phase4_exit_report.json"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--output", type=Path, default=Path("outputs/evaluation/freeze_manifest.json"))
    add_freeze_inputs(freeze)
    freeze.add_argument("--metric-reference", type=Path, default=Path("specs/005-experiment-evaluation/contracts/metric_reference.json"))
    freeze.add_argument("--expected-test-count", type=int, default=1045)
    freeze.set_defaults(handler=run_freeze)
    verify = commands.add_parser("verify-freeze")
    verify.add_argument("--manifest", type=Path, default=Path("outputs/evaluation/freeze_manifest.json"))
    add_frozen_inputs(verify)
    verify.set_defaults(handler=run_verify)
    generate = commands.add_parser("generate")
    generate.add_argument("--manifest", type=Path, required=True)
    generate.add_argument("--model", choices=("model_a", "model_b"), required=True)
    generate.add_argument("--checkpoint", type=Path, required=True)
    generate.add_argument("--output", type=Path, required=True)
    add_frozen_inputs(generate, required=True)
    generate.set_defaults(handler=generate_predictions)
    score = commands.add_parser("score")
    score.add_argument("--manifest", type=Path, default=Path("outputs/evaluation/freeze_manifest.json"))
    score.add_argument("--model-a-prediction", type=Path, default=Path("outputs/evaluation/model_a_test_predictions.jsonl"))
    score.add_argument("--model-b-prediction", type=Path, default=Path("outputs/evaluation/model_b_test_predictions.jsonl"))
    score.add_argument("--output-dir", type=Path, default=Path("outputs/evaluation"))
    score.add_argument("--schema", type=Path, default=Path("specs/005-experiment-evaluation/contracts/prediction.schema.json"))
    add_frozen_inputs(score)
    score.set_defaults(handler=run_score)
    errors = commands.add_parser("analyze-errors")
    errors.add_argument("--model-a-prediction", type=Path, default=Path("outputs/evaluation/model_a_test_predictions.jsonl"))
    errors.add_argument("--model-b-prediction", type=Path, default=Path("outputs/evaluation/model_b_test_predictions.jsonl"))
    errors.add_argument("--output", type=Path, default=Path("outputs/evaluation/error_analysis.jsonl"))
    errors.add_argument("--audit-output", type=Path, default=Path("outputs/evaluation/error_audit.json"))
    errors.add_argument("--weak-label-evidence", type=Path)
    errors.add_argument("--audit-limit", type=int, default=100)
    errors.set_defaults(handler=lambda args: print(json.dumps(write_error_analysis(args))))
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()