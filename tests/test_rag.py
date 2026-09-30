"""Unit tests for repository RAG filtering, chunking, indexing, and retrieval."""

import math
import tempfile
import unittest
from pathlib import Path
from typing import Sequence

from rag.chunking import chunk_file
from rag.indexing import index_repository
from rag.models import IndexedChunk, RepositoryFile, RetrievedChunk
from rag.retrieval import retrieve_relevant_chunks
from rag.scanner import scan_repository


class FakeEmbeddings:
    """A deterministic two-dimensional embedding model for unit tests."""

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, query: str) -> list[float]:
        return self._embed(query)

    @staticmethod
    def _embed(text: str) -> list[float]:
        lowered = text.casefold()
        return [1.0 if "auth" in lowered else 0.0, 1.0 if "database" in lowered else 0.0]


class FakeVectorStore:
    """A tiny in-memory store that exercises the indexer and retriever contract."""

    def __init__(self) -> None:
        self.chunks: dict[str, list[IndexedChunk]] = {}

    def replace_repository_chunks(
        self, repository_path: str, chunks: Sequence[IndexedChunk]
    ) -> int:
        self.chunks[repository_path] = list(chunks)
        return len(chunks)

    def search(
        self, repository_path: str, query_embedding: Sequence[float], limit: int
    ) -> list[RetrievedChunk]:
        def similarity(embedding: Sequence[float]) -> float:
            numerator = sum(left * right for left, right in zip(query_embedding, embedding))
            magnitude = math.sqrt(sum(value * value for value in query_embedding))
            magnitude *= math.sqrt(sum(value * value for value in embedding))
            return numerator / magnitude if magnitude else 0.0

        ranked = sorted(
            self.chunks.get(repository_path, []),
            key=lambda indexed: similarity(indexed.embedding),
            reverse=True,
        )[:limit]
        return [
            RetrievedChunk(
                file_path=indexed.chunk.file_path,
                text=indexed.chunk.text,
                score=similarity(indexed.embedding),
                metadata=indexed.chunk.metadata,
            )
            for indexed in ranked
        ]


class RepositoryRagTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_scanner_filters_generated_binary_large_and_ignored_files(self) -> None:
        (self.root / "src").mkdir()
        (self.root / "node_modules").mkdir()
        (self.root / "src" / "service.py").write_text("def run(): pass\n", encoding="utf-8")
        (self.root / "README.md").write_text("Project documentation\n", encoding="utf-8")
        (self.root / "src" / "app.min.js").write_text("generated", encoding="utf-8")
        (self.root / "src" / "binary.py").write_bytes(b"\x00not text")
        (self.root / "node_modules" / "dependency.js").write_text("ignored", encoding="utf-8")
        (self.root / "src" / "large.py").write_bytes(b"a" * 1_000_001)

        files = scan_repository(self.root)

        self.assertEqual([file.path for file in files], ["README.md", "src/service.py"])

    def test_chunking_keeps_path_line_ranges_and_overlap(self) -> None:
        source = RepositoryFile(
            path="src/example.py",
            content="alpha\nbeta\ngamma\ndelta\nepsilon\n",
        )

        chunks = chunk_file(source, chunk_size=12, overlap=5)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunk.file_path == "src/example.py" for chunk in chunks))
        self.assertEqual(chunks[0].start_line, 1)
        self.assertGreaterEqual(chunks[-1].end_line, chunks[-1].start_line)
        self.assertIn("beta", chunks[1].text)

    def test_indexing_and_retrieval_return_relevant_file_chunks(self) -> None:
        (self.root / "src").mkdir()
        (self.root / "src" / "auth.py").write_text(
            "def authenticate_user(token):\n    return token\n", encoding="utf-8"
        )
        (self.root / "src" / "database.py").write_text(
            "def open_database():\n    return None\n", encoding="utf-8"
        )
        embeddings = FakeEmbeddings()
        store = FakeVectorStore()

        result = index_repository(self.root, embeddings, store, chunk_size=200, overlap=20)
        matches = retrieve_relevant_chunks(
            "authentication", embeddings, store, root=self.root, limit=1
        )

        self.assertEqual(result.files_indexed, 2)
        self.assertEqual(result.chunks_indexed, 2)
        self.assertEqual(matches[0].file_path, "src/auth.py")
        self.assertGreater(matches[0].score, 0.9)

    def test_retrieval_rejects_empty_query(self) -> None:
        with self.assertRaises(ValueError):
            retrieve_relevant_chunks("", FakeEmbeddings(), FakeVectorStore(), root=self.root)


if __name__ == "__main__":
    unittest.main()
