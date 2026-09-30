"""Index the active repository into a vector store."""

import os
from pathlib import Path

from rag.chunking import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, chunk_file
from rag.embeddings import EmbeddingModel, LocalSentenceTransformerEmbeddings
from rag.models import IndexedChunk, IndexingResult
from rag.scanner import scan_repository
from rag.vector_store import VectorStore
from tools.repository import repository_root


def index_repository(
    root: Path,
    embedding_model: EmbeddingModel,
    vector_store: VectorStore,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> IndexingResult:
    """Scan, chunk, embed, and replace stored chunks for one repository."""
    repository = root.expanduser().resolve()
    files = scan_repository(repository)
    chunks = [
        chunk
        for source_file in files
        for chunk in chunk_file(source_file, chunk_size=chunk_size, overlap=overlap)
    ]
    embeddings = embedding_model.embed_documents([chunk.text for chunk in chunks])
    if len(embeddings) != len(chunks):
        raise ValueError("embedding model returned an unexpected number of vectors")

    indexed_chunks = [
        IndexedChunk(chunk=chunk, embedding=embedding)
        for chunk, embedding in zip(chunks, embeddings, strict=True)
    ]
    vector_store.replace_repository_chunks(str(repository), indexed_chunks)
    return IndexingResult(files_indexed=len(files), chunks_indexed=len(indexed_chunks))


def index_active_repository(
    embedding_model: EmbeddingModel,
    vector_store: VectorStore,
    root: Path | None = None,
) -> IndexingResult:
    """Index REPOSITORY_ROOT, or the current directory when it is unset."""
    return index_repository(root or repository_root(), embedding_model, vector_store)


def main() -> None:
    """Run local repository indexing from the command line."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("Set DATABASE_URL before indexing a repository.")

    from rag.vector_store import PostgresVectorStore

    result = index_active_repository(
        LocalSentenceTransformerEmbeddings(), PostgresVectorStore(database_url)
    )
    print(f"Indexed {result.files_indexed} files into {result.chunks_indexed} chunks.")


if __name__ == "__main__":
    main()
