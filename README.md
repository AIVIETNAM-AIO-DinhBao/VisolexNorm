# ViSoLexNorm

ViSoLexNorm normalizes noisy Vietnamese social-media text into standard Vietnamese. Its normalization models are fine-tuned from BARTpho-syllable and served through a React web application backed by FastAPI.

~~~text
hnay t đi hc
→ hôm nay tôi đi học
~~~

## Main pipeline

~~~text
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
Dev evaluation and model selection
        ↓
Selected Model C
        ↓
Local BARTpho inference
        ↓
FastAPI
        ↓
React frontend
~~~

Additional research analyses: Controlled factorial · C-max20 · Post-hoc A/B/C benchmark

- **Model A:** BARTpho-syllable fine-tuned on gold ViLexNorm training pairs.
- **Model B:** Model A continued with 8,372 gold and 8,372 pseudo-label examples per epoch from the initial 18,970 reviewed weak-label pool.
- **Model C:** Model A continued with the same per-epoch gold/pseudo balance using the expanded 64,813 reviewed weak-label pool.

Model C is selected for the application from common Dev ERR. Model B is the verified fallback. Test metrics are not used for application selection.

## Repository structure

~~~text
frontend/        React + Vite web interface
backend/         FastAPI launcher
visolexnorm/
  app/           inference, model loading, API, and model selection
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
report/          final project report and source
~~~

## Installation

Create a Python environment, then install the app dependencies:

~~~powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-app.txt
~~~

Other dependency sets:

- requirements-review.txt — local Gemini review and weak-label workflow.
- requirements-dev.txt — combined local development dependencies for the app and Gemini review workflows.
- requirements-kaggle.txt — Kaggle GPU training and evaluation notebooks.
- requirements-kaggle-offline.txt — controlled offline Kaggle notebooks; Kaggle supplies PyTorch/CUDA.

### Gemini review credentials

For review workflows, copy .env.example to .env and set GEMINI_API_KEYS to one or more comma-separated Gemini API keys. GEMINI_MODEL selects the review model. The review CLI loads these values from .env; never commit real keys.

## Model weights

Model weights and datasets are distributed separately because of file size. Download the required checkpoints and datasets from the shared Google Drive folder:

https://drive.google.com/drive/u/1/folders/1xJF9HTuBm0Na2yJsgRLgoc0BjaESe9BK

After downloading and extracting it, the repository root must contain:

~~~text
checkpoints/
├── model_c/   # default application model
└── model_b/   # verified fallback model
~~~

## Dataset

Raw and processed datasets are not bundled in Git. They are required for data preparation, training, and evaluation. Some historical experiment artifacts and large datasets/checkpoints are stored externally and are not tracked in Git.

~~~text
data/
├── raw/
├── intermediate/
└── processed/
~~~

Dataset download: use the shared [Google Drive folder](https://drive.google.com/drive/u/1/folders/1xJF9HTuBm0Na2yJsgRLgoc0BjaESe9BK).

## Run the application

~~~text
React → FastAPI → visolexnorm.app.inference → Model C / Model B fallback
~~~

Start the backend from the repository root:

~~~powershell
python backend/main.py
~~~

Start the frontend in another terminal:

~~~powershell
cd frontend
pnpm install --frozen-lockfile
pnpm dev
~~~

The frontend reads VITE_API_BASE_URL from frontend/.env; see frontend/.env.example for the default local API URL.

## Training and evaluation entrypoints

~~~powershell
python -m scripts.data --help
python -m scripts.candidates --help
python -m scripts.reviews --help
python -m scripts.weak_labels --help
python -m scripts.training --help
python -m scripts.evaluation --help
~~~

Some workflows require external datasets, checkpoints, Gemini credentials, or Kaggle artifacts.

## Results

### Dev model selection

| Model | ERR | F1 | Exact Match |
| --- | ---: | ---: | ---: |
| Model A | 0.603960 | 0.714903 | 0.520952 |
| Model B | 0.660891 | 0.753515 | 0.557143 |
| **Model C** | **0.670380** | **0.759233** | **0.561905** |

Model C ranks first on the common Dev split by ERR and is selected as the default application model. Model B is retained as the fallback. Test metrics are not used for application model selection.

Metrics: outputs/evaluation_dev/model_metrics.json. Selection: outputs/app/model_selection.json.

### Historical Phase 5 A/B Test evaluation

| Model | ERR | F1 |
| --- | ---: | ---: |
| Model A | 0.600250 | 0.718184 |
| Model B | 0.633111 | 0.742215 |

In this historical Phase 5 A/B comparison, Model B achieved the higher Test F1 and was retained over Model A at that stage.

### Post-hoc A/B/C Test benchmark

The post-hoc descriptive A/B/C benchmark was run after Model C existed, on a previously observed Test split. It is not promotion eligible, does not select Model C, and does not change the historical Phase 5 A/B decision.

| Model | ERR | F1 |
| --- | ---: | ---: |
| Model A | 0.600250 | 0.718184 |
| Model B | 0.633111 | 0.742215 |
| Model C | 0.664725 | 0.764993 |

### Additional analyses

- **Controlled factorial:** a Dev-only 2×2 follow-up crossed initial/expanded reviewed pools with 3/8-epoch horizons across three paired seeds. Under the frozen lowest-Dev-loss checkpoint rule, L8 was the strongest evaluated configuration.
- **C-max20:** an exploratory expanded-pool run with a 20-epoch maximum and early stopping selected epoch 9 and stopped at epoch 13. It did not improve the frozen L8 selected-checkpoint reference and is not promotion eligible.

## Report

The final project report and its source are available in report/.
