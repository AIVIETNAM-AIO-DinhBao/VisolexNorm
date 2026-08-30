"""Unified training command for Model A, Model B, and Model C."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from visolexnorm.training.mixtures import build_model_b_manifest, build_model_c_manifest
from visolexnorm.training.reports import finalize_model_c
from visolexnorm.training.strategies import ModelBTrainingStrategy, ModelCTrainingStrategy
from visolexnorm.training.trainer import run_mixture_training


def build_mixture(args: argparse.Namespace) -> None:
    root = args.repo_root.resolve()
    config = args.config if args.config.is_absolute() else root / args.config
    output = args.output if args.output.is_absolute() else root / args.output
    if args.model == "model_b":
        phase3 = args.phase3_manifest if args.phase3_manifest.is_absolute() else root / args.phase3_manifest
        manifest = build_model_b_manifest(root, config, phase3)
    else:
        manifest = build_model_c_manifest(root, config)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"output": str(output), "weak_label_count": manifest["weak_label_count"]}))


def train_mixture(args: argparse.Namespace) -> None:
    if args.model == "model_a":
        from visolexnorm.training.gold import run_gold_training

        run_gold_training(args)
        return
    strategy = ModelBTrainingStrategy() if args.model == "model_b" else ModelCTrainingStrategy()
    run_mixture_training(args, strategy)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    mixture = commands.add_parser("build-mixture")
    mixture.add_argument("--model", choices=("model_b", "model_c"), required=True)
    mixture.add_argument("--repo-root", type=Path, default=Path("."))
    mixture.add_argument("--config", type=Path)
    mixture.add_argument("--phase3-manifest", type=Path, default=Path("outputs/phase3_manifest.json"))
    mixture.add_argument("--output", type=Path)
    mixture.set_defaults(handler=build_mixture)
    train = commands.add_parser("train")
    train.add_argument("--model", choices=("model_a", "model_b", "model_c"), required=True)
    train.add_argument("--model-a-checkpoint", type=Path)
    train.add_argument("--data-dir", type=Path)
    train.add_argument("--mixture-manifest", type=Path)
    train.add_argument("--config", type=Path)
    train.add_argument("--work-dir", type=Path, default=Path("."))
    train.add_argument("--smoke-test", action="store_true")
    train.add_argument("--smoke-report", type=Path)
    train.add_argument("--checkpoint-path", type=Path)
    train.add_argument("--quiet", action="store_true")
    train.set_defaults(handler=train_mixture)
    finalize = commands.add_parser("finalize")
    finalize.add_argument("--model", choices=("model_c",), required=True)
    finalize.add_argument("--work-dir", type=Path, default=Path("."))
    finalize.add_argument("--exit-report", type=Path)
    finalize.set_defaults(handler=lambda args: print(json.dumps({"exit_report": str(finalize_model_c(args.work_dir.resolve(), args.exit_report)), "status": "completed"})))
    args = parser.parse_args()
    if args.command == "build-mixture":
        if args.config is None:
            args.config = Path(f"configs/{args.model}_config.json")
        if args.output is None:
            args.output = Path(f"outputs/{args.model}/training_mixture_manifest.json")
    elif args.command == "train":
        if args.model == "model_a":
            if args.data_dir is None:
                parser.error("Model A training requires --data-dir")
            if args.config is None:
                args.config = Path("configs/model_a_config.json")
        elif args.config is None:
            args.config = Path(f"configs/{args.model}_config.json")
        missing = [] if args.model == "model_a" else [name for name in ("model_a_checkpoint", "data_dir", "mixture_manifest") if getattr(args, name) is None]
        if missing:
            parser.error("training requires " + ", ".join("--" + name.replace("_", "-") for name in missing))
    args.handler(args)


if __name__ == "__main__":
    main()
