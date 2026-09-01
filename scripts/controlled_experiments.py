"""Freeze, build, run, and summarize Dev-only controlled training experiments."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from visolexnorm.training.controlled import (
    build_c_max20_manifest,
    build_factorial_manifests,
    freeze_protocol,
    run_controlled_training,
    summarize_factorial,
)


def _root(value: Path) -> Path:
    return value.resolve()


def freeze(args: argparse.Namespace) -> None:
    output = freeze_protocol(_root(args.repo_root), args.config.resolve(), args.cmax_config.resolve(), args.output.resolve())
    print(json.dumps({"protocol": str(output), "test_inputs_loaded": False}))


def build_factorial(args: argparse.Namespace) -> None:
    manifests = build_factorial_manifests(_root(args.repo_root), args.config.resolve(), args.protocol.resolve(), args.seed)
    for arm, manifest in manifests.items():
        path = args.output_dir.resolve() / f"seed_{args.seed}" / arm / "mixture_manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"seed": args.seed, "output_dir": str(args.output_dir.resolve()), "arms": sorted(manifests), "test_inputs_loaded": False}))


def build_cmax(args: argparse.Namespace) -> None:
    manifest = build_c_max20_manifest(_root(args.repo_root), args.config.resolve(), args.protocol.resolve(), args.seed)
    output = args.output.resolve(); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"seed": args.seed, "output": str(output), "test_inputs_loaded": False}))


def train(args: argparse.Namespace) -> None:
    run_controlled_training(args, optimization=args.optimization)


def summarize(args: argparse.Namespace) -> None:
    payload = summarize_factorial(args.input_root.resolve(), args.output.resolve())
    print(json.dumps({"output": str(args.output.resolve()), "seeds": payload["seeds"], "test_metrics_used": False}))


def _training_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model-a-checkpoint", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--allow-cpu", action="store_true")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    protocol = commands.add_parser("freeze-protocol")
    protocol.add_argument("--repo-root", type=Path, default=Path("."))
    protocol.add_argument("--config", type=Path, default=Path("configs/controlled_factorial_config.json"))
    protocol.add_argument("--cmax-config", type=Path, default=Path("configs/c_max20_early_stopping_config.json"))
    protocol.add_argument("--output", type=Path, default=Path("outputs/controlled_factorial/protocol.json"))
    protocol.set_defaults(handler=freeze)
    factorial = commands.add_parser("build-factorial")
    factorial.add_argument("--repo-root", type=Path, default=Path("."))
    factorial.add_argument("--config", type=Path, default=Path("configs/controlled_factorial_config.json"))
    factorial.add_argument("--protocol", type=Path, default=Path("outputs/controlled_factorial/protocol.json"))
    factorial.add_argument("--seed", type=int, required=True)
    factorial.add_argument("--output-dir", type=Path, default=Path("outputs/controlled_factorial"))
    factorial.set_defaults(handler=build_factorial)
    cmax = commands.add_parser("build-c-max20")
    cmax.add_argument("--repo-root", type=Path, default=Path("."))
    cmax.add_argument("--config", type=Path, default=Path("configs/c_max20_early_stopping_config.json"))
    cmax.add_argument("--protocol", type=Path, default=Path("outputs/controlled_factorial/protocol.json"))
    cmax.add_argument("--seed", type=int, default=2026)
    cmax.add_argument("--output", type=Path, default=Path("outputs/optimization/c_max20_es/seed_2026/mixture_manifest.json"))
    cmax.set_defaults(handler=build_cmax)
    factorial_train = commands.add_parser("train-factorial")
    _training_arguments(factorial_train); factorial_train.set_defaults(handler=train, optimization=False)
    optimization_train = commands.add_parser("train-c-max20")
    _training_arguments(optimization_train); optimization_train.set_defaults(handler=train, optimization=True)
    summary = commands.add_parser("summarize-factorial")
    summary.add_argument("--input-root", type=Path, default=Path("outputs/controlled_factorial"))
    summary.add_argument("--output", type=Path, default=Path("outputs/controlled_factorial/factorial_summary.json"))
    summary.set_defaults(handler=summarize)
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()