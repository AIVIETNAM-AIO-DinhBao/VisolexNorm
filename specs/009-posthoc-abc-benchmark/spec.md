# Phase 9 — Post-hoc A/B/C benchmark on observed ViLexNorm Test

## Scope

This phase generates exactly one Model C prediction file for the same 1,045
ViLexNorm Test rows already used by Phase 5. It reuses the frozen Model A and
Model B raw predictions and uses the same tokenizer, generation configuration,
and metric implementation.

## Scientific status

The ViLexNorm Test was observed before Model C was designed. This is therefore
an explicitly **post-hoc descriptive benchmark**, not an independent final
evaluation:

- it never modifies Phase 5 artifacts or Model B's selection;
- it cannot promote Model C automatically;
- it cannot be used to tune Model C after the result is observed;
- promotion still requires an independently frozen holdout.

## Required inputs

- Phase 5 freeze manifest and frozen raw Model A/B predictions;
- Phase 8 Model C artifact manifest, exit report, and checkpoint;
- `data/processed/vilexnorm_test.jsonl` with 1,045 ordered human-label rows;
- `configs/evaluation_generation_config.json` and frozen metric source.

## Outputs

```text
outputs/evaluation_abc_posthoc/
├── benchmark_manifest.json
├── model_c_test_predictions.jsonl
├── metrics.json
├── pairwise_deltas.json
├── comparison.md
├── benchmark_report.json
└── pairwise_error_analysis.jsonl
```

All outputs declare:

```json
{
  "evaluation_scope": "posthoc_previously_observed_vilexnorm_test",
  "test_previously_observed": true,
  "promotion_eligible": false
}
```