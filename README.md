# ViSoLexNorm

ViSoLexNorm normalizes noisy Vietnamese social-media text into standard Vietnamese. It is based on the BARTpho-syllable model and includes a React web application backed by a FastAPI service.

```text
hnay t đi hc
→ hôm nay tôi đi học
```

## Main pipeline

```text
Raw ViLexNorm / ViSoLex
        ↓
Data preparation
        ↓
Gold-only Model A
        ↓
Candidate generation
        ↓
Gemini review
        ↓
Weak-label construction
        ↓
Model B / Model C training
        ↓
Evaluation and model selection
        ↓
Local BARTpho inference
        ↓
FastAPI
        ↓
React frontend
```

Model C is the application checkpoint selected from common Dev metrics. Model B remains the verified fallback. Historical Phase 5 A/B evaluation selected Model B by F1; the later A/B/C benchmark is descriptive and does not change that historical decision.

## Repository structure

```text
frontend/        React + Vite web interface
backend/         FastAPI launcher
visolexnorm/
  app/           inference, model loading, API, model selection, Gradio UI
  common/        shared I/O, artifact, progress, and runtime utilities
  data/          dataset preparation and validation
  candidates/    Model A candidate generation and review manifests
  review/        Gemini-assisted review, policy, and cache
  weak_labels/   weak-label construction and audit
  training/      Model A/B/C and controlled-training utilities
  evaluation/    metrics, evaluation, and model selection
configs/         project configurations
scripts/         command-line entrypoints
specs/           runtime JSON schemas and contracts used by the pipeline
notebooks/       Kaggle training and evaluation notebooks
outputs/         experiment and evaluation artifacts
prompts/         Gemini review prompts
report/          report source and artifacts
```

## Installation

Create a Python environment, then install the application dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-app.txt
```

For the local Gemini review and weak-label workflow:

```powershell
pip install -r requirements-review.txt
```

Kaggle training and evaluation notebooks use `requirements-kaggle.txt`. The controlled offline Kaggle notebooks also require `requirements-kaggle-offline.txt`.

## Model weights

Model weights are distributed separately because of file size. The verified application checkpoint bundle is available from:

https://www.kaggle.com/datasets/dinhbaobao/visolexnorm-app-checkpoints-v1/versions/1

After downloading and extracting it, the repository root must contain:

```text
checkpoints/
├── model_c/   # default application model
└── model_b/   # verified fallback model
```

## Dataset

Raw and processed datasets are not bundled in Git. They are required only for data preparation, training, and evaluation workflows.

```text
data/
├── raw/
├── intermediate/
└── processed/
```

TODO: add submission dataset link.

## Run the application

The primary web path is:

```text
React → FastAPI → visolexnorm.app inference → local BARTpho checkpoint
```

Start the backend from the repository root:

```powershell
python backend/main.py
```

Start the frontend in another terminal:

```powershell
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

The frontend reads `VITE_API_BASE_URL` from `frontend/.env`; see `frontend/.env.example` for the default local API URL.

The repository also retains a local Gradio interface:

```powershell
python -m visolexnorm.app.web
```

## Training and evaluation entrypoints

```powershell
python -m scripts.data --help
python -m scripts.candidates --help
python -m scripts.reviews --help
python -m scripts.weak_labels --help
python -m scripts.training --help
python -m scripts.evaluation --help
```

These workflows require the external datasets, checkpoints, and Kaggle resources described above.

## Results

Historical Phase 5 frozen A/B Test results:

| Model | ERR | F1 |
| --- | ---: | ---: |
| Model A | 0.600250 | 0.718184 |
| Model B | 0.633111 | 0.742215 |

The common A/B/C Test benchmark reports Model C at F1 0.764993 and Model B at F1 0.742215. Model C was selected for the application from common Dev metrics, not from Test metrics.

## Report

The project report source and rendered PDF are retained in `report/`. Additional submitted PDF artifacts remain at the repository root.
