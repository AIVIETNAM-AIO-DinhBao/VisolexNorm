# ViSoLexNorm maintenance guide

This is the active reference for repository architecture, commands, refactor
invariants, and local artifact retention. Historical `spec.md`, `plan.md`, and
`tasks.md` files describe the source revision in which each research phase was
run; they are not rewritten when maintenance commands change.

## Architecture map

All commands are run from the repository root with module execution:

```text
python -m scripts.<domain> <subcommand> ...
```

| Entry point | Package implementation | Responsibility |
|---|---|---|
| `scripts.data` | `visolexnorm.data`, `visolexnorm.common` | Data preparation, validation, protected hashes |
| `scripts.candidates` | `visolexnorm.candidates` | Model A candidate generation, manifests, audit |
| `scripts.reviews` | `visolexnorm.review` | Gemini provider, cache, policy, review pipeline |
| `scripts.weak_labels` | `visolexnorm.weak_labels` | Initial/expanded weak-label build and audit |
| `scripts.training` | `visolexnorm.training` | Model A/B/C training, mixtures, reports |
| `scripts.evaluation` | `visolexnorm.evaluation` | Phase 5 freeze, prediction, scoring, errors |

`scripts/evaluation_metrics.py` is an intentional exception. It is the frozen
Phase 5 scientific metric implementation and must remain at that path and
byte-equivalent to the historical inventory. The evaluation CLI injects it into
the package scoring service; the package does not copy the implementation.

CLI modules parse arguments and dispatch to domain services. They must remain
importable without loading Torch, Transformers, Google GenAI, or a GPU runtime.

## Current commands

```text
python -m scripts.data --help
python -m scripts.candidates --help
python -m scripts.reviews --help
python -m scripts.weak_labels --help
python -m scripts.training --help
python -m scripts.evaluation --help
```

Direct file execution such as `python scripts/data.py` is no longer an active
interface. Module execution makes the repository root import boundary explicit
and avoids `sys.path` mutation.

## Historical command map

| Historical entry point | Active command |
|---|---|
| `scripts/prepare_vilexnorm.py` | `python -m scripts.data prepare-vilexnorm` |
| `scripts/prepare_visolex.py` | `python -m scripts.data prepare-visolex` |
| `scripts/check_data.py` | `python -m scripts.data validate` |
| `scripts/export_protected_hashes.py` | `python -m scripts.data export-protected-hashes` |
| `scripts/generate_candidates.py` | `python -m scripts.candidates generate` |
| `scripts/generate_model_a_candidates.py` | `python -m scripts.candidates generate` |
| `scripts/select_review_manifest.py` | `python -m scripts.candidates select-review` |
| `scripts/select_remaining_review_manifest.py` | `python -m scripts.candidates select-remaining` |
| `scripts/audit_candidate_full_run.py` | `python -m scripts.candidates audit` |
| `scripts/review_candidates.py` | `python -m scripts.reviews run` |
| `scripts/review_with_gemini.py` | Removed legacy reviewer; use `python -m scripts.reviews run` |
| `scripts/export_pilot_audit.py` | `python -m scripts.reviews export-pilot` |
| `scripts/freeze_review_prompt.py` | `python -m scripts.reviews freeze-prompt` |
| `scripts/build_weak_labels.py` | `python -m scripts.weak_labels build-initial` |
| `scripts/build_expanded_weak_labels.py` | `python -m scripts.weak_labels build-expanded` |
| `scripts/audit_weak_labels.py` | `python -m scripts.weak_labels audit` |
| `scripts/build_model_b_mixture.py` | `python -m scripts.training build-mixture --model model_b` |
| `scripts/build_model_c_mixture.py` | `python -m scripts.training build-mixture --model model_c` |
| `scripts/train_model_a.py` | `python -m scripts.training train --model model_a` |
| `scripts/train_model_b.py` | `python -m scripts.training train --model model_b` |
| `scripts/train_model_c.py` | `python -m scripts.training train --model model_c` |
| `scripts/train_model_c.py --finalize` | `python -m scripts.training finalize --model model_c` |
| `scripts/freeze_experiment.py` | `python -m scripts.evaluation freeze` |
| `scripts/freeze_experiment.py --verify` | `python -m scripts.evaluation verify-freeze` |
| `scripts/generate_test_predictions.py` | `python -m scripts.evaluation generate` |
| `scripts/evaluate_predictions.py` | `python -m scripts.evaluation score` |
| `scripts/build_error_analysis.py` | `python -m scripts.evaluation analyze-errors` |

## Refactor invariants

Maintenance changes must preserve all of the following:

1. `outputs/evaluation/best_model.json` remains the historical Phase 5 A/B
   selection artifact and names Model B. Do not rewrite it.
2. `outputs/app/model_selection.json` is the current application selection
   artifact. It names Model C after the verified Phase 9 post-hoc benchmark and
   retains Model B as verified rollback.
3. No maintenance task calls Gemini, trains a model, or runs GPU prediction
   generation unless explicitly approved as a new research run.
4. Frozen prompts, lexical policy, configs, schemas, and historical manifests
   are not reformatted or regenerated during source maintenance.
5. `scripts/evaluation_metrics.py` remains byte-for-byte frozen. Text inventory
   verification normalizes line endings to LF, as recorded by Phase 5.
6. Model selection uses `manifest["model_selection_rule"]`. In particular, the
   historical `lower_ERR` rule is not rewritten to the newer template rule.
7. Model B/C mixture membership, order, seed, wrap/replacement behavior, content
   hash, and serialized bytes remain reproducible.
8. Existing SQLite review caches retain schema, identity, and resume semantics.
   Never delete `-wal` or `-shm` files independently of a closed database.
9. Phase 5 comparison contains Model A and Model B only.
10. Artifact cleanup never deletes the only copy of an artifact that has not
    been verified in external storage.

## Verification gates

Before committing maintenance changes:

```text
python -m pytest -q
python -m scripts.evaluation verify-freeze
git diff --exit-code -- scripts/evaluation_metrics.py
git diff --check
```

## Post-hoc A/B/C benchmark

Phase 9 adds a descriptive Model C result on the already observed Phase 5
ViLexNorm Test. Its isolated namespace is `outputs/evaluation_abc_posthoc/`.
It reuses frozen Model A/B predictions and generates only Model C predictions:

```text
python -m scripts.evaluation posthoc-verify
python -m scripts.evaluation posthoc-generate --model model_c
python -m scripts.evaluation posthoc-score
python -m scripts.evaluation posthoc-analyze-errors
```

This benchmark is intentionally marked
`posthoc_previously_observed_vilexnorm_test` and does not modify the Phase 5
`best_model.json`, freeze manifest, metrics, or error analysis. The explicit
Phase 10 app decision is created from its verified evidence:

```text
python -m scripts.evaluation posthoc-promote
python -m visolexnorm.app.inference --smoke
```

The promotion artifact keeps Model B rollback metadata. See
`specs/009-posthoc-abc-benchmark/` and `specs/010-model-c-app-promotion/`.

Training mixture and Model C report reconstruction tests require the ignored
local artifacts. Score/error replay must write to a temporary directory rather
than overwrite `outputs/evaluation`.

## Artifact retention policy

### Keep local for application and rollback

- `checkpoints/model_c/`
- `checkpoints/model_b/`
- `outputs/app/model_selection.json`
- `outputs/evaluation/best_model.json`
- `outputs/evaluation/freeze_manifest.json`
- Model B raw Test predictions and minimum app/test data

### Frozen provenance; externalize only after verified backup

- Model A checkpoint and `model_a_artifacts.zip`
- `visolex_model_a_candidates.zip`
- Model C checkpoint and transfer bundle
- any artifact named by Phase 3, Phase 5, or Phase 8 manifests

Copy to external storage, compare byte size and SHA-256, record the destination
in `docs/artifact-retention.json`, and only then remove the workspace copy.

### Safe local cleanup after inventory

- `.pytest_cache/`
- project `__pycache__/` directories (not individual caches inside `.venv`)
- `.tmp/*.pid`, `.tmp/*.out`, `.tmp/*.err`
- verified duplicate extracted bundles
- superseded pilot audit/report revisions not referenced by a frozen manifest
- obsolete recovery snapshots after current SQLite integrity and provenance are
  verified

The machine-readable status and cleanup result are recorded in
`docs/artifact-retention.json`.

### Local cleanup status

The post-refactor cleanup removed local caches, Phase 8 temporary process
files, superseded pilot revisions, the obsolete recovery snapshot, and the
verified duplicate extracted Model C mixture manifest. Model A/B/C checkpoints
and all provenance ZIP files remain in the workspace because no external
destination was configured. Their inventory status is `externalize-pending`;
they must not be removed until a copied-file SHA-256 verification is recorded.