"""Make the project package available to legacy direct script entry points."""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_project_root() -> None:
    """Add the repository root once when a script is executed by file path."""
    root = str(Path(__file__).resolve().parents[1])
    if root not in sys.path:
        sys.path.insert(0, root)