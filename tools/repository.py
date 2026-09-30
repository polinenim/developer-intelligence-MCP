"""Shared helpers for locating and walking the active repository."""

import os
from pathlib import Path


IGNORED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
}


def repository_root() -> Path:
    """Return the repository root configured for this server process."""
    configured_root = os.environ.get("REPOSITORY_ROOT", ".")
    return Path(configured_root).expanduser().resolve()
