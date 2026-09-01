"""Unified Phase 5 freeze, generation, scoring, and error-analysis command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from visolexnorm.evaluation import benchmark
from visolexnorm.evaluation.errors import write_error_analysis
from visolexnorm.evaluation.freeze import build_manifest, verify_manifest
from visolexnorm.evaluation.predictions import generate_predictions
from visolexnorm.evaluation.scoring import evaluate
from visolexnorm.app.selection import build_dev_selection
from visolexnorm.evaluation.dev_selection import score_dev_predictions, write_dev_metrics


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


def run_posthoc_freeze(args: argparse.Namespace) -> None:
    if args.output.exists():
        raise FileExistsError(f"Post-hoc manifest already exists: {args.output}; use posthoc-verify, never overwrite it")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(benchmark.build_manifest(args), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"frozen": True, "manifest": str(args.output), "promotion_eligible": False}))


def run_posthoc_verify(args: argparse.Namespace) -> None:
    benchmark.verify_manifest(json.loads(args.manifest.read_text(encoding="utf-8")), args)
    print(json.dumps({"verified": True, "manifest": str(args.manifest), "promotion_eligible": False}))


def run_posthoc_score(args: argparse.Namespace) -> None:
    from scripts.evaluation_metrics import OFFICIAL_REFERENCE, evaluate_records

    result = benchmark.score_benchmark(args, evaluate_records=evaluate_records, metric_reference=OFFICIAL_REFERENCE)
    print(json.dumps({"descriptive_leader": result["report"]["descriptive_leader"], "promotion_eligible": False, "metrics": result["metrics"]["models"]}, ensure_ascii=False, indent=2))


def run_posthoc_errors(args: argparse.Namespace) -> None:
    count = benchmark.write_pairwise_error_analysis(args)
    print(json.dumps({"records": count, "output": str(args.output), "promotion_eligible": False}))


def run_dev_score(args: argparse.Namespace) -> None:
    from scripts.evaluation_metrics import evaluate_records

    payload = score_dev_predictions({
        "model_a": args.model_a_prediction,
        "model_b": args.model_b_prediction,
        "model_c": args.model_c_prediction,
    }, evaluate_records=evaluate_records)
    write_dev_metrics(payload, args.output)
    print(json.dumps({"selected_model": payload["selected_model"], "output": str(args.output)}))


def run_dev_select(args: argparse.Namespace) -> None:
    selection = build_dev_selection(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(selection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"selected_model": selection["selected_model"], "fallback_model": selection["fallback_model"], "output": str(args.output)}))


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


def add_posthoc_inputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, default=Path("configs/posthoc_abc_benchmark_config.json"))
    parser.add_argument("--phase5-manifest", type=Path, default=Path("outputs/evaluation/freeze_manifest.json"))
    parser.add_argument("--phase5-metrics", type=Path, default=Path("outputs/evaluation/test_metrics.json"))
    parser.add_argument("--model-a-prediction", type=Path, default=Path("outputs/evaluation/model_a_test_predictions.jsonl"))
    parser.add_argument("--model-b-prediction", type=Path, default=Path("outputs/evaluation/model_b_test_predictions.jsonl"))
    parser.add_argument("--model-a-checkpoint", type=Path, default=Path("checkpoints/model_a"))
    parser.add_argument("--model-b-checkpoint", type=Path, default=Path("checkpoints/model_b"))
    parser.add_argument("--model-c-checkpoint", type=Path, default=Path("checkpoints/model_c"))
    parser.add_argument("--model-c-artifact-manifest", type=Path, default=Path("outputs/model_c/artifact_manifest.json"))
    parser.add_argument("--model-c-exit-report", type=Path, default=Path("outputs/model_c/phase8_exit_report.json"))
    parser.add_argument("--test", type=Path, default=Path("data/processed/vilexnorm_test.jsonl"))
    parser.add_argument("--generation-config", type=Path, default=Path("configs/evaluation_generation_config.json"))
    parser.add_argument("--metric-code", type=Path, default=Path("scripts/evaluation_metrics.py"))
    parser.add_argument("--phase3-manifest", type=Path, default=Path("outputs/phase3_manifest.json"))
    parser.add_argument("--phase4-exit-report", type=Path, default=Path("outputs/model_b/phase4_exit_report.json"))
    parser.add_argument("--schema", type=Path, default=Path("specs/009-posthoc-abc-benchmark/contracts/prediction.schema.json"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    dev_score = commands.add_parser("dev-score", help="Score aligned Model A/B/C Dev predictions")
    dev_score.add_argument("--model-a-prediction", type=Path, default=Path("outputs/model_a/dev_predictions.jsonl"))
    dev_score.add_argument("--model-b-prediction", type=Path, default=Path("outputs/model_b/dev_predictions.jsonl"))
    dev_score.add_argument("--model-c-prediction", type=Path, default=Path("outputs/model_c/dev_predictions.jsonl"))
    dev_score.add_argument("--output", type=Path, default=Path("outputs/evaluation_dev/model_metrics.json"))
    dev_score.set_defaults(handler=run_dev_score)
    dev_select = commands.add_parser("dev-select", help="Select the application checkpoint from Dev metrics")
    dev_select.add_argument("--dev-metrics", type=Path, default=Path("outputs/evaluation_dev/model_metrics.json"))
    dev_select.add_argument("--model-a-checkpoint", type=Path, default=Path("checkpoints/model_a"))
    dev_select.add_argument("--model-b-checkpoint", type=Path, default=Path("checkpoints/model_b"))
    dev_select.add_argument("--model-c-checkpoint", type=Path, default=Path("checkpoints/model_c"))
    dev_select.add_argument("--output", type=Path, default=Path("outputs/app/model_selection.json"))
    dev_select.set_defaults(handler=run_dev_select)
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
    posthoc_freeze = commands.add_parser("posthoc-freeze", help="Freeze non-promotional A/B/C post-hoc benchmark inputs")
    posthoc_freeze.add_argument("--output", type=Path, default=Path("outputs/evaluation_abc_posthoc/benchmark_manifest.json"))
    add_posthoc_inputs(posthoc_freeze)
    posthoc_freeze.set_defaults(handler=run_posthoc_freeze)
    posthoc_verify = commands.add_parser("posthoc-verify", help="Verify frozen post-hoc benchmark inputs")
    posthoc_verify.add_argument("--manifest", type=Path, default=Path("outputs/evaluation_abc_posthoc/benchmark_manifest.json"))
    add_posthoc_inputs(posthoc_verify)
    posthoc_verify.set_defaults(handler=run_posthoc_verify)
    posthoc_generate = commands.add_parser("posthoc-generate", help="Generate frozen Model C post-hoc predictions on GPU")
    posthoc_generate.add_argument("--manifest", type=Path, default=Path("outputs/evaluation_abc_posthoc/benchmark_manifest.json"))
    posthoc_generate.add_argument("--model", choices=("model_c",), required=True)
    posthoc_generate.add_argument("--checkpoint", type=Path, default=Path("checkpoints/model_c"))
    posthoc_generate.add_argument("--output", type=Path, default=Path("outputs/evaluation_abc_posthoc/model_c_test_predictions.jsonl"))
    add_posthoc_inputs(posthoc_generate)
    posthoc_generate.set_defaults(handler=benchmark.generate_model_c_predictions)
    posthoc_score = commands.add_parser("posthoc-score", help="Score frozen A/B predictions with one Model C post-hoc prediction")
    posthoc_score.add_argument("--manifest", type=Path, default=Path("outputs/evaluation_abc_posthoc/benchmark_manifest.json"))
    posthoc_score.add_argument("--model-c-prediction", type=Path, default=Path("outputs/evaluation_abc_posthoc/model_c_test_predictions.jsonl"))
    posthoc_score.add_argument("--output-dir", type=Path, default=Path("outputs/evaluation_abc_posthoc"))
    add_posthoc_inputs(posthoc_score)
    posthoc_score.set_defaults(handler=run_posthoc_score)
    posthoc_errors = commands.add_parser("posthoc-analyze-errors", help="Write post-hoc A/B/C pairwise error analysis")
    posthoc_errors.add_argument("--model-a-prediction", type=Path, default=Path("outputs/evaluation/model_a_test_predictions.jsonl"))
    posthoc_errors.add_argument("--model-b-prediction", type=Path, default=Path("outputs/evaluation/model_b_test_predictions.jsonl"))
    posthoc_errors.add_argument("--model-c-prediction", type=Path, default=Path("outputs/evaluation_abc_posthoc/model_c_test_predictions.jsonl"))
    posthoc_errors.add_argument("--output", type=Path, default=Path("outputs/evaluation_abc_posthoc/pairwise_error_analysis.jsonl"))
    posthoc_errors.set_defaults(handler=run_posthoc_errors)
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()