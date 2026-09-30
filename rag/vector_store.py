"""PostgreSQL and pgvector storage for repository text chunks."""

import json
import math
from typing import Protocol, Sequence

from rag.models import IndexedChunk, RetrievedChunk


class VectorStore(Protocol):
    """Storage interface shared by indexing and retrieval."""

    def replace_repository_chunks(
        self, repository_path: str, chunks: Sequence[IndexedChunk]
    ) -> int:
        """Replace all stored chunks for one repository."""

    def search(
        self, repository_path: str, query_embedding: Sequence[float], limit: int
    ) -> list[RetrievedChunk]:
        """Return the most similar chunks for one repository."""


class PostgresVectorStore:
    """Store and retrieve chunks with PostgreSQL's pgvector extension."""

    def __init__(self, database_url: str) -> None:
        if not database_url.strip():
            raise ValueError("database_url must not be empty")
        self.database_url = database_url

    def replace_repository_chunks(
        self, repository_path: str, chunks: Sequence[IndexedChunk]
    ) -> int:
        """Replace every indexed chunk for repository_path in one transaction."""
        if not chunks:
            self._delete_repository_if_table_exists(repository_path)
            return 0

        dimensions = len(chunks[0].embedding)
        if dimensions == 0 or any(len(chunk.embedding) != dimensions for chunk in chunks):
            raise ValueError("all chunk embeddings must have the same non-zero dimensions")

        rows = [
            (
                repository_path,
                indexed.chunk.file_path,
                indexed.chunk.text,
                indexed.chunk.start_line,
                indexed.chunk.end_line,
                json.dumps(indexed.chunk.metadata),
                _vector_literal(indexed.embedding),
            )
            for indexed in chunks
        ]

        with self._connect() as connection:
            with connection.cursor() as cursor:
                self._ensure_schema(cursor, dimensions)
                cursor.execute(
                    "DELETE FROM repository_chunks WHERE repository_path = %s",
                    (repository_path,),
                )
                cursor.executemany(
                    """
                    INSERT INTO repository_chunks
                        (repository_path, file_path, chunk_text, start_line, end_line,
                         metadata, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::vector)
                    """,
                    rows,
                )
        return len(rows)

    def search(
        self, repository_path: str, query_embedding: Sequence[float], limit: int = 5
    ) -> list[RetrievedChunk]:
        """Retrieve chunks ordered by cosine similarity."""
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        vector = _vector_literal(query_embedding)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT file_path, chunk_text, metadata,
                           1 - (embedding <=> %s::vector) AS score
                    FROM repository_chunks
                    WHERE repository_path = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (vector, repository_path, vector, limit),
                )
                rows = cursor.fetchall()

        return [
            RetrievedChunk(
                file_path=file_path,
                text=chunk_text,
                score=float(score),
                metadata=_metadata_dict(metadata),
            )
            for file_path, chunk_text, metadata, score in rows
        ]

    def _delete_repository_if_table_exists(self, repository_path: str) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass('public.repository_chunks')")
                if cursor.fetchone()[0] is not None:
                    cursor.execute(
                        "DELETE FROM repository_chunks WHERE repository_path = %s",
                        (repository_path,),
                    )

    @staticmethod
    def _ensure_schema(cursor, dimensions: int) -> None:
        if dimensions > 2_000:
            raise ValueError("pgvector supports at most 2,000 vector dimensions")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS repository_chunks (
                id BIGSERIAL PRIMARY KEY,
                repository_path TEXT NOT NULL,
                file_path TEXT NOT NULL,
                chunk_text TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                metadata JSONB NOT NULL,
                embedding vector({dimensions}) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS repository_chunks_embedding_hnsw_idx
            ON repository_chunks USING hnsw (embedding vector_cosine_ops)
            """
        )

    def _connect(self):
        try:
            from psycopg import connect
        except ImportError as error:
            raise RuntimeError("Install psycopg before using PostgreSQL storage.") from error
        return connect(self.database_url)


def _vector_literal(values: Sequence[float]) -> str:
    """Format a finite numeric vector for PostgreSQL's vector input syntax."""
    if not values:
        raise ValueError("embedding must not be empty")
    numbers = [float(value) for value in values]
    if not all(math.isfinite(value) for value in numbers):
        raise ValueError("embedding values must be finite")
    return "[" + ",".join(str(value) for value in numbers) + "]"


def _metadata_dict(value) -> dict:
    if isinstance(value, dict):
        return value
    return json.loads(value)
