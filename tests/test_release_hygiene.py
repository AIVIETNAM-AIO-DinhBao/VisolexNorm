"""Release guards for notebooks and dependency separation."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).parents[1]
NOTEBOOKS = sorted((ROOT / "notebooks").glob("*.ipynb"))
PERSONAL_PATH = re.compile(r"[A-Za-z]:\\Users\\|/home/[^/]+|/Users/[^/]+")
API_KEY = re.compile(r"AIza[0-9A-Za-z_-]{20,}")


def test_notebooks_are_clean_json_without_outputs_or_secrets() -> None:
    assert NOTEBOOKS
    for path in NOTEBOOKS:
        payload = json.loads(path.read_text(encoding="utf-8"))
        text = path.read_text(encoding="utf-8")
        assert not PERSONAL_PATH.search(text), path
        assert not API_KEY.search(text), path
        assert "GEMINI_API_KEYS=" not in text, path
        for cell in payload.get("cells", []):
            if cell.get("cell_type") == "code":
                assert cell.get("execution_count") is None, path
                assert cell.get("outputs") == [], path
                assert "execution" not in cell.get("metadata", {}), path
        assert "papermill" not in payload.get("metadata", {}), path


def test_dependency_files_keep_runtime_scopes_separate() -> None:
    review = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    inference = (ROOT / "requirements-inference.txt").read_text(encoding="utf-8")
    kaggle = (ROOT / "requirements-kaggle.txt").read_text(encoding="utf-8")
    development = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")

    assert "google-genai" in review and "pytest" not in review and "torch" not in review
    assert "gradio" in inference and "google-genai" not in inference
    assert "datasets" in kaggle and "gradio" not in kaggle and "google-genai" not in kaggle
    assert "-r requirements.txt" in development
    assert "-r requirements-inference.txt" in development
    assert "pytest" in development