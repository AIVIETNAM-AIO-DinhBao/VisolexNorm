"""FastAPI REST API server for ViSoLexNorm lexical normalization."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from visolexnorm.app import inference

LOGGER = logging.getLogger(__name__)


class NormalizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000, description="Văn bản tiếng Việt cần chuẩn hóa")


class NormalizeResponse(BaseModel):
    status: str = "success"
    original_text: str
    normalized_text: str
    latency_ms: float


class HealthResponse(BaseModel):
    status: str = "healthy"
    service: str = "visolexnorm-api"


class ModelInfoResponse(BaseModel):
    schema_version: int
    selected_model: str
    rollback_model: str
    checkpoint_path: str
    fallback_applied: bool


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-warm runtime and model weights on server startup."""
    LOGGER.info("Starting ViSoLexNorm API service. Pre-warming model runtime...")
    try:
        # Load runtime configuration and pre-load model into RAM
        smoke = inference.smoke_report()
        LOGGER.info("Runtime verified. Active model: %s (Checkpoint: %s)", smoke["selected_model"], smoke["checkpoint_path"])
        # Perform 1 dummy normalization to warm up torch layers
        inference.normalize("chào bạn")
        LOGGER.info("Model pre-warming complete. API is ready to accept requests.")
    except Exception as error:
        LOGGER.warning("Model pre-warming deferred or failed: %s", error)
    yield
    LOGGER.info("Shutting down ViSoLexNorm API service...")
    inference.clear_runtime_cache()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="ViSoLexNorm API",
        description="REST API chuẩn hóa từ vựng tiếng Việt mạng xã hội bằng mô hình BARTpho",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Enable CORS for local web development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "*",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health", response_model=HealthResponse, tags=["System"])
    async def health_check() -> HealthResponse:
        """Health check endpoint."""
        return HealthResponse()

    @app.get("/api/model-info", response_model=ModelInfoResponse, tags=["System"])
    async def get_model_info() -> ModelInfoResponse:
        """Return information about the active normalized model checkpoint."""
        try:
            report = inference.smoke_report()
            return ModelInfoResponse(
                schema_version=report["schema_version"],
                selected_model=report["selected_model"],
                rollback_model=report["rollback_model"],
                checkpoint_path=report["checkpoint_path"],
                fallback_applied=report["fallback_applied"],
            )
        except Exception as error:
            LOGGER.exception("Failed to retrieve model info: %s", error)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Không thể đọc thông tin mô hình: {error}",
            )

    @app.post("/api/normalize", response_model=NormalizeResponse, tags=["Normalization"])
    async def normalize_endpoint(payload: NormalizeRequest) -> NormalizeResponse:
        """Normalize Vietnamese social media teencode/slang to standard text."""
        text = payload.text.strip()
        if not text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vui lòng nhập văn bản cần chuẩn hóa.",
            )

        start_time = time.perf_counter()
        try:
            normalized = inference.normalize(text)
        except inference.InputValidationError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error),
            )
        except Exception as error:
            LOGGER.exception("Normalization error for input '%s': %s", text, error)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Lỗi khi xử lý chuẩn hóa trên server.",
            )

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        return NormalizeResponse(
            status="success",
            original_text=text,
            normalized_text=normalized,
            latency_ms=round(latency_ms, 2),
        )

    return app


app = create_app()


def main() -> None:
    """Run API server locally via uvicorn."""
    import uvicorn

    uvicorn.run("visolexnorm.app.api:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
