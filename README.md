# Developer Intelligence MCP

A developer-focused MCP server that reads, searches, and semantically retrieves information from a local source repository.

It combines MCP repository tools with a local RAG pipeline to help an AI assistant understand a codebase and retrieve relevant source code.

## Requirements

- Python 3.10 or newer
- PostgreSQL with the pgvector extension

## Technology Stack

- Python
- MCP
- PostgreSQL
- pgvector
- Sentence Transformers
- `all-MiniLM-L6-v2`

## Setup

From this directory, create and activate a virtual environment, then install the dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Repository Configuration

Set `REPOSITORY_ROOT` to the local repository that the server should inspect.

If `REPOSITORY_ROOT` is not set, the current working directory is used.

```powershell
$env:REPOSITORY_ROOT = 'C:\path\to\your\repository'
```

## MCP Server

Start the MCP server with:

```powershell
python -m server.mcp_server
```

The server uses MCP's stdio transport. An MCP host can launch `python -m server.mcp_server` with this project directory as its working directory and `REPOSITORY_ROOT` set to the target repository.

### Available MCP Tools

#### `read_file(path)`

Reads a UTF-8 text file using its repository-relative path.

#### `search_code(query)`

Searches the repository for a case-insensitive text query and returns matching repository-relative file paths.

Search skips common generated directories, ignored repository content, and files larger than 1 MB.

## Repository RAG

The RAG pipeline scans the configured repository, filters unnecessary files, splits source files into text chunks, generates local embeddings, and stores the chunks and embeddings in PostgreSQL with pgvector.

```text
Repository
    ↓
File Scanner
    ↓
File Filtering
    ↓
Text Chunks
    ↓
Local Embeddings
    ↓
PostgreSQL + pgvector
    ↓
Similarity Search
    ↓
Relevant Repository Chunks
```

The local embedding model is:

```text
sentence-transformers/all-MiniLM-L6-v2
```

The model runs locally and downloads its model files on first use.

Each stored chunk includes repository information such as:

- File path
- Chunk text
- Start and end line information
- Embedding
- Similarity metadata during retrieval

## Database Setup

Create a PostgreSQL database with pgvector available:

```powershell
createdb developer_intelligence
```

Set the database and repository environment variables:

```powershell
$env:DATABASE_URL = 'postgresql://postgres:postgres@localhost:5432/developer_intelligence'
$env:REPOSITORY_ROOT = 'C:\path\to\your\repository'
```

Run the repository indexer:

```powershell
python -m rag.indexing
```

The indexing process creates the required `vector` extension, database table, and HNSW index automatically.

## Retrieval

Relevant repository chunks can be retrieved using:

```python
retrieve_relevant_chunks(query, embedding_model, vector_store)
```

The retrieval function returns relevant chunks together with file paths, line metadata, and similarity scores.

These results provide the repository evidence used by the AI layer.

## Project Structure

```text
developer-intelligence-mcp/
├── rag/
│   ├── chunking.py
│   ├── embeddings.py
│   ├── file_filter.py
│   ├── indexing.py
│   ├── retrieval.py
│   ├── scanner.py
│   └── vector_store.py
├── server/
│   └── mcp_server.py
├── tools/
│   ├── repository.py
│   ├── read_file.py
│   └── search_code.py
├── tests/
├── requirements.txt
└── README.md
```

## Verification

The repository RAG pipeline has been verified with a real PostgreSQL + pgvector database.

- 19 repository files indexed
- 41 chunks created
- 384-dimensional embeddings stored
- PostgreSQL `vector` extension verified
- HNSW similarity-search index verified
- Retrieval returned relevant repository chunks
- Automated test suite: `**8/8 tests passing**`

Run the tests with:

```powershell
python -m unittest discover -s tests -v
```
