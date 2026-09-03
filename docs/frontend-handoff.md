# Frontend handoff

## Fixed application boundary

| Item | Fixed value |
|---|---|
| Default model | Model C (`APP-DEFAULT`) |
| Fallback model | Model B (`APP-FALLBACK`) |
| Model selection split | Dev only |
| Runtime LLM/API calls | None |
| C-max20 | Exploratory only; do not use in the app |

The authoritative records are `release/training-closure.json` and
`outputs/app/model_selection.json`. Artifact IDs, rather than local paths or raw hashes, are used
in handoff documentation.

## Frontend-safe scope

- `visolexnorm/app/web.py`;
- presentation CSS, static assets, UI copy, and screenshots;
- README and user-facing frontend documentation.

## Do not modify

- `outputs/app/model_selection.json`;
- `release/manifest.json`, `release/checkpoint-inventory.json`, and `release/training-closure.json`;
- `checkpoints/model_c/`, `checkpoints/model_b/`;
- historical evaluation/freeze artifacts;
- training configs, frozen factorial artifacts, or C-max20 analysis.

## Required checks before a frontend handoff commit

```powershell
python -m scripts.verify_training_closure
python -m pytest -q
python -m visolexnorm.app.inference --smoke
```

The local app must remain loopback-only, offline-capable after checkpoint installation, and free
of Gemini/API-key dependencies.

`release/manifest.json` belongs to the historical `v1.0.0` snapshot. Run its strict verifier only
from a checkout of tag `v1.0.0` with the released checkpoints restored; the current closure branch
uses `verify_training_closure.py` as its application/checkpoint verifier.