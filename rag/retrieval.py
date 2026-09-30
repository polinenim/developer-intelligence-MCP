"""Retrieve relevant repository chunks for a natural-language query."""

from pathlib import Path

from rag.embeddings import EmbeddingModel
from rag.models import RetrievedChunk
from rag.vector_store import VectorStore
from tools.repository import repository_root


def retrieve_relevant_chunks(
    query: str,
    embedding_model: EmbeddingModel,
    vector_store: VectorStore,
    root: Path | None = None,
    limit: int = 5,
) -> list[RetrievedChunk]:
    """Return the most relevant indexed chunks for query from the active repository."""
    if not query.strip():
        raise ValueError("query must not be empty")
    repository = (root or repository_root()).expanduser().resolve()
    return vector_store.search(str(repository), embedding_model.embed_query(query), limit)
