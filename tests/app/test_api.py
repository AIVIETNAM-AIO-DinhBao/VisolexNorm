"""Unit and contract tests for ViSoLexNorm FastAPI REST API endpoints."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from visolexnorm.app.api import app
from visolexnorm.app.inference import InputValidationError


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "visolexnorm-api"


def test_model_info_endpoint(client: TestClient) -> None:
    response = client.get("/api/model-info")
    assert response.status_code == 200
    data = response.json()
    assert data["selected_model"] in {"model_c", "model_b"}
    assert "checkpoint_path" in data


def test_normalize_endpoint_success(client: TestClient) -> None:
    with patch("visolexnorm.app.inference.normalize", return_value="mình không biết hôm nay đi học không"):
        response = client.post("/api/normalize", json={"text": "mik ko bt hnay đi hc ko"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["original_text"] == "mik ko bt hnay đi hc ko"
        assert data["normalized_text"] == "mình không biết hôm nay đi học không"
        assert "latency_ms" in data
        assert isinstance(data["latency_ms"], (int, float))


def test_normalize_endpoint_empty_text(client: TestClient) -> None:
    response = client.post("/api/normalize", json={"text": "   "})
    assert response.status_code in {400, 422}


def test_normalize_endpoint_validation_error(client: TestClient) -> None:
    with patch("visolexnorm.app.inference.normalize", side_effect=InputValidationError("Văn bản vượt quá giới hạn 128 token.")):
        response = client.post("/api/normalize", json={"text": "văn bản quá dài"})
        assert response.status_code == 400
        assert "Văn bản vượt quá giới hạn" in response.json()["detail"]
