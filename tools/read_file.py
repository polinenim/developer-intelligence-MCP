"""Read one text file inside a configured repository root."""

from pathlib import Path


def _resolve_repository_file(root: Path, relative_path: str) -> Path:
    if not relative_path.strip():
        raise ValueError("path must not be empty")

    repository = root.expanduser().resolve()
    candidate = (repository / relative_path).resolve()
    if not candidate.is_relative_to(repository):
        raise ValueError("path must point to a file inside the repository")
    if not candidate.is_file():
        raise FileNotFoundError(f"file not found: {relative_path}")
    return candidate


def read_repository_file(root: Path, relative_path: str) -> str:
    """Read a UTF-8 file by its repository-relative path."""
    file_path = _resolve_repository_file(root, relative_path)
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"file is not UTF-8 text: {relative_path}") from error
