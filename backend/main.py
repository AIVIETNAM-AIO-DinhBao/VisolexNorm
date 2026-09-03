"""
VietNorm Backend Server Entrypoint.

This script launches the FastAPI server from `visolexnorm.app.api`.
It automatically adds the project root to `sys.path` and ensures the
working directory is set to the repository root so that relative configs
and checkpoints load seamlessly.
"""

import os
from pathlib import Path
import sys
import uvicorn

# Ensure repository root is on sys.path and set as current working directory
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.chdir(REPO_ROOT)

# Import FastAPI application
from visolexnorm.app.api import app  # noqa: E402


def run(host: str = "127.0.0.1", port: int = 8000, reload: bool = True) -> None:
    """Run the FastAPI backend using Uvicorn."""
    print(f"Starting VietNorm Backend on http://{host}:{port} ...")
    uvicorn.run("visolexnorm.app.api:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    run()
