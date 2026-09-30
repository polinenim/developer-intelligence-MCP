"""Scan a repository and return supported UTF-8 source files."""

import os
from pathlib import Path

from rag.file_filter import MAX_FILE_BYTES, should_index_file, should_skip_directory
from rag.models import RepositoryFile


def scan_repository(root: Path) -> list[RepositoryFile]:
    """Read supported text files below root in deterministic path order."""
    repository = root.expanduser().resolve()
    if not repository.is_dir():
        raise NotADirectoryError(f"repository root not found: {repository}")

    files: list[RepositoryFile] = []
    for current, directories, filenames in os.walk(repository, followlinks=False):
        directories[:] = sorted(
            name for name in directories if not should_skip_directory(name)
        )
        for filename in sorted(filenames):
            candidate = Path(current, filename)
            if not candidate.resolve().is_relative_to(repository):
                continue
            if not should_index_file(candidate):
                continue
            content = _read_text_file(candidate)
            if content is not None:
                files.append(
                    RepositoryFile(
                        path=candidate.relative_to(repository).as_posix(),
                        content=content,
                    )
                )
    return files


def _read_text_file(path: Path) -> str | None:
    """Read a small UTF-8 text file and ignore binary or unreadable files."""
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        with path.open("rb") as file:
            if b"\x00" in file.read(8_192):
                return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
