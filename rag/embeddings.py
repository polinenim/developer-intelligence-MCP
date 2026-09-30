"""Local embedding model adapter used by the repository RAG pipeline."""

from typing import Protocol, Sequence


DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class EmbeddingModel(Protocol):
    """The small interface needed by indexing and retrieval."""

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a group of document texts."""

    def embed_query(self, query: str) -> list[float]:
        """Embed one search query."""


class LocalSentenceTransformerEmbeddings:
    """Embed text locally with a Sentence Transformers model."""

    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL) -> None:
        self.model_name = model_name
        self._model = None

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Return normalized embeddings for source chunks."""
        if not texts:
            return []
        vectors = self._get_model().encode(
            list(texts), normalize_embeddings=True, show_progress_bar=False
        )
        return [[float(value) for value in vector] for vector in vectors]

    def embed_query(self, query: str) -> list[float]:
        """Return a normalized embedding for one non-empty query."""
        if not query.strip():
            raise ValueError("query must not be empty")
        return self.embed_documents([query])[0]

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as error:
                raise RuntimeError(
                    "Install sentence-transformers before creating local embeddings."
                ) from error
            self._model = SentenceTransformer(self.model_name, device="cpu")
        return self._model
