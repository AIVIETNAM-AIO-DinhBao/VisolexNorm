# Phase 5 Test Comparison

| Model | Samples | ERR (error reduction) | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| model_a | 1045 | 0.703037 | 0.733999 | 0.703037 | 0.718184 |
| model_b | 1045 | 0.723847 | 0.761538 | 0.723847 | 0.742215 |

**Selected model:** `model_b` by `higher_f1`.

Frozen historical rule: `higher_f1, lower_ERR, model_a`. ERR tie-break was not used when F1 selected a winner.
