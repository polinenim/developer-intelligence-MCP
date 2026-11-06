"""Retrieve relevant repository chunks for a natural-language query."""

import re
from pathlib import Path

from rag.embeddings import EmbeddingModel
from rag.models import RetrievedChunk
from rag.vector_store import VectorStore
from tools.repository import repository_root


_LEXICAL_STOP_WORDS = frozenset(
    "a an and are as at be by can do does for from how in is it of on or the "
    "to was we what when where which who why with"
    .split()
)


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
    if limit <= 0:
        raise ValueError("limit must be greater than zero")
    repository = (root or repository_root()).expanduser().resolve()
    matches = vector_store.search(str(repository), embedding_model.embed_query(query), limit)
    query_terms = set(re.findall(r"[a-z0-9]+", query.casefold())) - _LEXICAL_STOP_WORDS
    relevant = [match for match in matches if match.score > 0]
    return sorted(
        relevant,
        key=lambda match: (
            match.score,
            len(
                query_terms
                & (set(re.findall(r"[a-z0-9]+", match.text.casefold())) - _LEXICAL_STOP_WORDS)
            ),
        ),
        reverse=True,
    )
