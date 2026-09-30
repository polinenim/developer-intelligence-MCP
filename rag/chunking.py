"""Split source text into overlapping chunks while preserving file locations."""

from rag.models import RepositoryFile, TextChunk


DEFAULT_CHUNK_SIZE = 1_200
DEFAULT_CHUNK_OVERLAP = 200


def chunk_file(
    source_file: RepositoryFile,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[TextChunk]:
    """Split one source file into line-aware, overlapping text chunks."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be zero or greater and smaller than chunk_size")

    text = source_file.content
    if not text.strip():
        return []

    chunks: list[TextChunk] = []
    start = 0
    text_length = len(text)
    while start < text_length:
        end = min(start + chunk_size, text_length)
        if end < text_length:
            line_break = text.rfind("\n", start + 1, end)
            if line_break > start:
                end = line_break + 1

        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(
                TextChunk(
                    file_path=source_file.path,
                    text=chunk_text,
                    start_line=text.count("\n", 0, start) + 1,
                    end_line=text.count("\n", 0, max(start, end - 1)) + 1,
                )
            )

        if end == text_length:
            break
        next_start = end - overlap
        start = next_start if next_start > start else end

    return chunks
