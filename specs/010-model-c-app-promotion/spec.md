# Phase 10 — Promote Model C as the application checkpoint

## Decision

Model C is the current application checkpoint after the Phase 9 A/B/C
post-hoc benchmark. Model B remains a verified rollback checkpoint.

## Evidence

- Model C F1: `0.7649928263988521`
- Model B F1: `0.7422145328719723`
- F1 delta C−B: `0.022778293526879878`
- Bootstrap 95% CI for F1 delta: `[0.012063470298296575, 0.03322807721199306]`
- Phase 9 benchmark manifest:
  `b29cf856c61f4f190d6c4607f79b6a9b13b6d05be72f58d3eb8c0276610c240e`

## Boundaries

- `outputs/evaluation/best_model.json` remains the historical Phase 5 A/B
  selection artifact and continues to name Model B.
- `outputs/app/model_selection.json` is the current application selection
  artifact and names Model C with Model B rollback metadata.
- App selection does not modify Phase 5 provenance or claim that Phase 9 was
  an independently unseen evaluation.
- Runtime inference must verify the selected checkpoint inventory. If Model C
  is missing or differs from its approved inventory, it must fall back to the
  verified Model B checkpoint.

## Local runtime

Install `requirements-inference.txt`, then run
`python -m visolexnorm.app.inference --smoke` before serving local inference.
`python -m visolexnorm.app.inference --text "..."` performs a real local
tokenizer/model load and generation; it never calls an LLM API.