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

SENSITIVE_FILE_SUFFIXES = {".key", ".p12", ".pem", ".pfx"}


def is_sensitive_repository_file(path: Path) -> bool:
    """Return whether a repository file should not be exposed to tools or indexing."""
    name = path.name.casefold()
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return True
    if path.suffix.casefold() in SENSITIVE_FILE_SUFFIXES:
        return True
    return any(part.casefold() == "secrets" for part in path.parts)


def repository_root() -> Path:
    """Return the repository root configured for this server process."""
    configured_root = os.environ.get("REPOSITORY_ROOT", ".")
    return Path(configured_root).expanduser().resolve()
