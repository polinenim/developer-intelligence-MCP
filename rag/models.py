"""Data objects used by the repository RAG pipeline."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RepositoryFile:
    """A text file read from a repository."""

    path: str
    content: str


@dataclass(frozen=True)
class TextChunk:
    """A file fragment that retains its source path and line range."""

    file_path: str
    text: str
    start_line: int
    end_line: int

    @property
    def metadata(self) -> dict[str, int]:
        """Return metadata stored alongside this chunk."""
        return {"start_line": self.start_line, "end_line": self.end_line}


@dataclass(frozen=True)
class IndexedChunk:
    """A text chunk paired with its vector embedding."""

    chunk: TextChunk
    embedding: list[float]


@dataclass(frozen=True)
class RetrievedChunk:
    """A source chunk returned by similarity search."""

    file_path: str
    text: str
    score: float
    metadata: dict[str, Any]


@dataclass(frozen=True)
class IndexingResult:
    """A small summary of one repository indexing run."""

    files_indexed: int
    chunks_indexed: int
