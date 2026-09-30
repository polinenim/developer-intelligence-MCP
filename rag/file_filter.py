"""Rules for selecting useful repository files for RAG indexing."""

from pathlib import Path

from tools.repository import IGNORED_DIRECTORIES


MAX_FILE_BYTES = 1_000_000

SUPPORTED_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".css",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".kt",
    ".md",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".rst",
    ".sh",
    ".sql",
    ".swift",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

SUPPORTED_FILENAMES = {"dockerfile", "license", "makefile", "readme"}
GENERATED_SUFFIXES = (".generated", ".min.css", ".min.js", ".map")
GENERATED_FILENAMES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock"}


def should_skip_directory(name: str) -> bool:
    """Return whether a directory should be excluded from indexing."""
    return name.startswith(".") or name in IGNORED_DIRECTORIES


def should_index_file(path: Path) -> bool:
    """Return whether a path looks like useful source or documentation text."""
    name = path.name.casefold()
    if name in GENERATED_FILENAMES or name.endswith(GENERATED_SUFFIXES):
        return False
    return name in SUPPORTED_FILENAMES or path.suffix.casefold() in SUPPORTED_EXTENSIONS
