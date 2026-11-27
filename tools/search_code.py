"""Search text files under a configured repository root."""

import os
from pathlib import Path

from tools.repository import IGNORED_DIRECTORIES, is_sensitive_repository_file

MAX_FILE_BYTES = 1_000_000


def search_repository(root: Path, query: str) -> list[str]:
    """Return sorted relative paths for files containing query, ignoring case."""
    if not query:
        raise ValueError("query must not be empty")

    repository = root.expanduser().resolve()
    if not repository.is_dir():
        raise NotADirectoryError(f"repository root not found: {repository}")

    needle = query.casefold()
    matches: list[str] = []

    for current, directories, filenames in os.walk(repository, followlinks=False):
        directories[:] = sorted(
            name
            for name in directories
            if name not in IGNORED_DIRECTORIES and not name.startswith(".")
        )
        for filename in filenames:
            path = Path(current, filename)
            try:
                resolved_path = path.resolve()
                if not resolved_path.is_relative_to(repository):
                    continue
                if is_sensitive_repository_file(resolved_path):
                    continue
                if resolved_path.stat().st_size > MAX_FILE_BYTES:
                    continue
                content = resolved_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if needle in content.casefold():
                matches.append(path.relative_to(repository).as_posix())

    return sorted(matches)
