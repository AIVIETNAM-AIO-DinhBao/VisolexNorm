# Quickstart — Phase 9 post-hoc A/B/C benchmark

This benchmark uses the previously observed Phase 5 ViLexNorm Test. It is
descriptive only: it cannot change `outputs/evaluation/best_model.json` or
promote Model C.

1. Verify the frozen benchmark inputs locally:

   ```powershell
   python -m scripts.evaluation posthoc-verify
   ```

   The frozen local manifest is:

   ```text
   outputs/evaluation_abc_posthoc/benchmark_manifest.json
   SHA-256: b29cf856c61f4f190d6c4607f79b6a9b13b6d05be72f58d3eb8c0276610c240e
   ```

   Copy this manifest unchanged to the private Kaggle input dataset.

2. Run `notebooks/evaluate_model_c_posthoc_kaggle.ipynb` once on a Kaggle GPU.
   It verifies the benchmark manifest and exports only
   `model_c_test_predictions.jsonl`.

3. Download the Model C prediction file to:

   ```text
   outputs/evaluation_abc_posthoc/model_c_test_predictions.jsonl
   ```

4. Score and inspect the descriptive comparison locally:

   ```powershell
   python -m scripts.evaluation posthoc-score
   python -m scripts.evaluation posthoc-analyze-errors
   ```

The output report will retain `promotion_eligible=false`; a new independently
frozen holdout is still required before Model C can replace Model B.