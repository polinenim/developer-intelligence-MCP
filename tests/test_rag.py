"""Unit tests for repository RAG filtering, chunking, indexing, and retrieval."""

import math
import tempfile
import unittest
from pathlib import Path
from typing import Sequence
from unittest.mock import Mock

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

    def test_scanner_normalizes_newlines_in_text_files(self) -> None:
        (self.root / "src").mkdir()
        (self.root / "src" / "line_endings.py").write_bytes(b"first\r\nsecond\rthird\n")

        files = scan_repository(self.root)

        self.assertEqual(files[0].content, "first\nsecond\nthird\n")

    def test_chunking_keeps_path_line_ranges_and_overlap(self) -> None:
        source = RepositoryFile(
            path="src/example.py",
            content="alpha\nbeta\ngamma\ndelta\nepsilon\n",
        )

        chunks = chunk_file(source, chunk_size=12, overlap=5)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunk.file_path == "src/example.py" for chunk in chunks))
        self.assertEqual(
            [(chunk.start_line, chunk.end_line) for chunk in chunks],
            [(1, 2), (2, 3), (3, 4), (4, 4), (5, 5)],
        )
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
        self.assertEqual(matches[0].metadata, {"start_line": 1, "end_line": 2})
        self.assertGreater(matches[0].score, 0.9)

    def test_reindexing_updates_changed_content_and_preserves_other_file_chunks(self) -> None:
        (self.root / "src").mkdir()
        changed_file = self.root / "src" / "changed.py"
        changed_file.write_text("def old_version():\n    return 'old payload'\n", encoding="utf-8")
        (self.root / "src" / "stable.py").write_text(
            "def stable_version():\n    return 'stable payload'\n", encoding="utf-8"
        )
        embeddings = FakeEmbeddings()
        store = FakeVectorStore()
        repository_path = str(self.root.resolve())

        index_repository(self.root, embeddings, store, chunk_size=200, overlap=20)
        stable_chunks_before = [
            indexed
            for indexed in store.chunks[repository_path]
            if indexed.chunk.file_path == "src/stable.py"
        ]

        changed_file.write_text(
            "def new_version():\n    return 'updated payload'\n", encoding="utf-8"
        )
        index_repository(self.root, embeddings, store, chunk_size=200, overlap=20)

        changed_chunks = [
            indexed
            for indexed in store.chunks[repository_path]
            if indexed.chunk.file_path == "src/changed.py"
        ]
        stable_chunks_after = [
            indexed
            for indexed in store.chunks[repository_path]
            if indexed.chunk.file_path == "src/stable.py"
        ]

        self.assertEqual(len(changed_chunks), 1)
        self.assertIn("updated payload", changed_chunks[0].chunk.text)
        self.assertNotIn("old payload", changed_chunks[0].chunk.text)
        self.assertEqual(stable_chunks_after, stable_chunks_before)

    def test_reindexing_removes_deleted_file_chunks_and_preserves_existing_chunks(self) -> None:
        (self.root / "src").mkdir()
        removed_file = self.root / "src" / "removed.py"
        removed_file.write_text("def removed():\n    return 'stale content'\n", encoding="utf-8")
        (self.root / "src" / "existing.py").write_text(
            "def existing():\n    return 'current content'\n", encoding="utf-8"
        )
        embeddings = FakeEmbeddings()
        store = FakeVectorStore()
        repository_path = str(self.root.resolve())

        index_repository(self.root, embeddings, store, chunk_size=200, overlap=20)
        existing_chunks_before = [
            indexed
            for indexed in store.chunks[repository_path]
            if indexed.chunk.file_path == "src/existing.py"
        ]
        removed_file.unlink()

        index_repository(self.root, embeddings, store, chunk_size=200, overlap=20)

        remaining_chunks = store.chunks[repository_path]
        existing_chunks_after = [
            indexed
            for indexed in remaining_chunks
            if indexed.chunk.file_path == "src/existing.py"
        ]
        self.assertFalse(any(indexed.chunk.file_path == "src/removed.py" for indexed in remaining_chunks))
        self.assertEqual(existing_chunks_after, existing_chunks_before)

    def test_indexing_empty_repository_reports_zero_and_clears_store(self) -> None:
        store = FakeVectorStore()

        result = index_repository(self.root, FakeEmbeddings(), store)

        self.assertEqual(result.files_indexed, 0)
        self.assertEqual(result.chunks_indexed, 0)
        self.assertEqual(store.chunks[str(self.root.resolve())], [])

    def test_indexing_only_ignored_or_unsupported_files_reports_zero(self) -> None:
        (self.root / "node_modules").mkdir()
        (self.root / "node_modules" / "dependency.py").write_text(
            "def ignored(): pass\n", encoding="utf-8"
        )
        (self.root / "notes.unsupported").write_text("not indexable", encoding="utf-8")
        store = FakeVectorStore()

        result = index_repository(self.root, FakeEmbeddings(), store)

        self.assertEqual(result.files_indexed, 0)
        self.assertEqual(result.chunks_indexed, 0)
        self.assertEqual(store.chunks[str(self.root.resolve())], [])

    def test_indexing_scanned_file_without_chunks_reports_file_and_clears_stale_chunks(self) -> None:
        source_file = self.root / "empty.py"
        source_file.write_text("def previous_content(): pass\n", encoding="utf-8")
        store = FakeVectorStore()
        repository_path = str(self.root.resolve())
        index_repository(self.root, FakeEmbeddings(), store)
        self.assertTrue(store.chunks[repository_path])

        source_file.write_text(" \n\t\n", encoding="utf-8")
        result = index_repository(self.root, FakeEmbeddings(), store)

        self.assertEqual(result.files_indexed, 1)
        self.assertEqual(result.chunks_indexed, 0)
        self.assertEqual(store.chunks[repository_path], [])

    def test_reindexing_after_all_files_are_removed_clears_stale_chunks(self) -> None:
        source_file = self.root / "source.py"
        source_file.write_text("def indexed_content(): pass\n", encoding="utf-8")
        store = FakeVectorStore()
        repository_path = str(self.root.resolve())
        initial_result = index_repository(self.root, FakeEmbeddings(), store)
        self.assertEqual(initial_result.chunks_indexed, 1)

        source_file.unlink()
        result = index_repository(self.root, FakeEmbeddings(), store)

        self.assertEqual(result.files_indexed, 0)
        self.assertEqual(result.chunks_indexed, 0)
        self.assertEqual(store.chunks[repository_path], [])

    def test_retrieval_matches_different_user_and_code_terminology(self) -> None:
        (self.root / "src").mkdir()
        (self.root / "src" / "auth.py").write_text(
            "def authenticate_user(username, password):\n"
            "    return identity_provider.verify_credentials(username, password)\n",
            encoding="utf-8",
        )
        (self.root / "src" / "database.py").write_text(
            "def connect_to_database(connection_string):\n"
            "    return psycopg.connect(connection_string)\n",
            encoding="utf-8",
        )

        class TerminologyTestEmbeddings:
            """Map login and authentication terms to one deterministic concept."""

            @staticmethod
            def _embed(text: str) -> list[float]:
                lowered = text.casefold()
                if any(term in lowered for term in ("login", "authenticate", "credential")):
                    return [1.0, 0.0]
                if "database" in lowered:
                    return [0.0, 1.0]
                return [0.0, 0.0]

            def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
                return [self._embed(text) for text in texts]

            def embed_query(self, query: str) -> list[float]:
                return self._embed(query)

        embeddings = TerminologyTestEmbeddings()
        store = FakeVectorStore()
        index_repository(self.root, embeddings, store)

        matches = retrieve_relevant_chunks(
            "How do we validate a person's login details before granting access?",
            embeddings,
            store,
            root=self.root,
            limit=1,
        )

        self.assertEqual(matches[0].file_path, "src/auth.py")

    def test_retrieval_evaluation_returns_expected_files_at_top_one(self) -> None:
        (self.root / "src").mkdir()
        (self.root / "src" / "auth.py").write_text(
            "def verify_credentials(username, password):\n    return True\n",
            encoding="utf-8",
        )
        (self.root / "src" / "database.py").write_text(
            "def open_database_connection(url):\n    return psycopg.connect(url)\n",
            encoding="utf-8",
        )
        (self.root / "src" / "config.py").write_text(
            "def read_runtime_options(path):\n    return json.loads(Path(path).read_text())\n",
            encoding="utf-8",
        )

        class EvaluationEmbeddings:
            """Map related query and code terms to deterministic concept vectors."""

            _terms = {
                "authentication": ("login", "credential", "password"),
                "database": ("database", "postgres", "connection", "connect"),
                "configuration": ("settings", "options", "config"),
            }
            _vectors = {
                "authentication": [1.0, 0.0, 0.0],
                "database": [0.0, 1.0, 0.0],
                "configuration": [0.0, 0.0, 1.0],
            }

            @classmethod
            def _embed(cls, text: str) -> list[float]:
                lowered = text.casefold()
                for concept, terms in cls._terms.items():
                    if any(term in lowered for term in terms):
                        return cls._vectors[concept]
                return [0.0, 0.0, 0.0]

            def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
                return [self._embed(text) for text in texts]

            def embed_query(self, query: str) -> list[float]:
                return self._embed(query)

        evaluations = (
            ("How do we check a user's login before granting access?", "src/auth.py"),
            ("Where does the service open a PostgreSQL connection?", "src/database.py"),
            ("Where are the application's settings loaded from?", "src/config.py"),
        )
        embeddings = EvaluationEmbeddings()
        store = FakeVectorStore()
        index_repository(self.root, embeddings, store)

        correct_top_one = 0
        for query, expected_file in evaluations:
            with self.subTest(query=query):
                matches = retrieve_relevant_chunks(
                    query, embeddings, store, root=self.root, limit=3
                )
                top_file = matches[0].file_path if matches else None
                correct_top_one += top_file == expected_file
                self.assertEqual(top_file, expected_file)

        self.assertEqual(correct_top_one / len(evaluations), 1.0)

    def test_unrelated_query_excludes_zero_similarity_chunks(self) -> None:
        (self.root / "src").mkdir()
        (self.root / "src" / "auth.py").write_text(
            "def authenticate_user(username, password):\n    return True\n",
            encoding="utf-8",
        )
        (self.root / "src" / "database.py").write_text(
            "def connect_to_database(connection_string):\n    return None\n",
            encoding="utf-8",
        )

        class OrthogonalTestEmbeddings:
            """Give unrelated query and repository chunks orthogonal vectors."""

            def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
                return [
                    [1.0, 0.0, 0.0] if "authenticate" in text else [0.0, 1.0, 0.0]
                    for text in texts
                ]

            def embed_query(self, query: str) -> list[float]:
                return [0.0, 0.0, 1.0]

        embeddings = OrthogonalTestEmbeddings()
        store = FakeVectorStore()
        index_repository(self.root, embeddings, store)

        matches = retrieve_relevant_chunks(
            "What is the weather forecast?",
            embeddings,
            store,
            root=self.root,
            limit=5,
        )

        self.assertEqual(matches, [])

    def test_retrieval_rejects_empty_query(self) -> None:
        with self.assertRaises(ValueError):
            retrieve_relevant_chunks("", FakeEmbeddings(), FakeVectorStore(), root=self.root)

    def test_retrieval_rejects_non_positive_limit_before_embedding_or_search(self) -> None:
        for limit in (0, -1):
            embedding_model = Mock()
            vector_store = Mock()
            with self.subTest(limit=limit):
                with self.assertRaisesRegex(ValueError, "limit must be greater than zero"):
                    retrieve_relevant_chunks(
                        "authentication",
                        embedding_model,
                        vector_store,
                        root=self.root,
                        limit=limit,
                    )
                embedding_model.embed_query.assert_not_called()
                vector_store.search.assert_not_called()


if __name__ == "__main__":
    unittest.main()
