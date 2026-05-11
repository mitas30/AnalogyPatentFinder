"""Shared path setup for repository-level administrative tools."""

from __future__ import annotations

import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = REPO_ROOT / "server"


def add_server_to_path() -> None:
    server_path = str(SERVER_ROOT)
    if server_path not in sys.path:
        sys.path.insert(0, server_path)


def activate_server_context() -> None:
    add_server_to_path()
    os.chdir(SERVER_ROOT)


def resolve_repo_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate
