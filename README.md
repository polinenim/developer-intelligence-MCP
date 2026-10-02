# Developer Intelligence MCP

A focused repository intelligence project that combines a small MCP server,
local repository analysis tools, a repository RAG pipeline (local embeddings
stored in PostgreSQL+pgvector), and a minimal AI agent built on Gemini via
LangChain.

This repository provides:

- MCP repository tools to read and search files inside a configured
    repository root (`server/mcp_server.py`).
- A repository RAG pipeline that splits files into chunks, computes local
    embeddings (Sentence Transformers `all-MiniLM-L6-v2`), and stores vectors
    in PostgreSQL with the `pgvector` extension.
- A lightweight AI agent foundation that uses the Gemini chat model via
    LangChain to answer repository questions using retrieved evidence.

The project is intentionally small and keeps the agent focused on
repository analysis: evidence is returned with file path and line ranges.

## Requirements

- Python 3.10 or newer
- PostgreSQL with the `pgvector` extension

## Quick setup

Create and activate a virtual environment, then install the project's
dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Set the repository and database environment variables used by the tools:

```powershell
$env:REPOSITORY_ROOT = 'C:\path\to\your\repository'
$env:DATABASE_URL = 'postgresql://postgres:postgres@localhost:5432/developer_intelligence'
```

## MCP repository tools

Start the MCP server to expose repository utilities over MCP's stdio
transport:

```powershell
python -m server.mcp_server
```

The server registers two simple tools:

- `read_file(path)` — read a UTF-8 text file by repository-relative path.
- `search_code(query)` — search repository files for a case-insensitive
    text query and return matching repository-relative file paths.

These tools reuse the implementations in `tools/read_file.py` and
`tools/search_code.py` and operate relative to `REPOSITORY_ROOT`.

## Repository RAG and local embeddings

The RAG pipeline scans the configured repository, filters files, splits
source files into text chunks, computes local sentence-transformer
embeddings, and persists chunk metadata and vectors in PostgreSQL using
the `pgvector` extension. Each chunk stores:

- repository file path
- chunk text
- start and end line information
- embedding vector

Use the indexer to populate the database:

```powershell
python -m rag.indexing
```

Retrieval is available via `rag.retrieval.retrieve_relevant_chunks(...)`,
which returns chunks along with file paths, start/end line metadata, and
similarity scores used as evidence by the AI agent.

## Gemini + LangChain (LLM)

LLM configuration is centralized in `server/llm_config.py`. The project uses
LangChain's `ChatGoogleGenerativeAI` wrapper for Gemini. The agent obtains
the model using `agent.get_agent_model()` which delegates to the LLM
initializer. Tests and the agent code avoid making real API calls by
accepting a provided fake model during tests.

## AI agent and question/answer flow

The agent composes answers using this simple flow:

1. Retrieve relevant chunks from the repository RAG via
     `retrieve_relevant_chunks(query, embedding_model, vector_store)`.
2. If no chunks are returned, fall back to `search_code` and `read_file`
     to collect candidate evidence from repository files.
3. Compose a short prompt containing the evidence and the question and
     invoke the configured Gemini chat model via LangChain.
4. Return the model's answer along with `sources` describing file paths
     and start/end line ranges for each piece of evidence.

The agent's implementation lives under `agent/` and the core answer flow
is in `agent/core.py`. A convenience wrapper in `agent/agent.py` uses the
server's `REPOSITORY_ROOT` so the agent runs against the same repository
configured for the MCP server.

## Project structure

```text
developer-intelligence-mcp/
├── rag/                 # RAG pipeline: chunking, embeddings, indexing, retrieval
├── server/              # LLM config and MCP server exposing repository tools
├── agent/               # Minimal agent foundation and core answer flow
├── tools/               # read_file, search_code, repository helpers
├── tests/               # unit tests
├── requirements.txt
└── README.md
```

## Tests

Run the unit tests with:

```powershell
python -m unittest discover -s tests -v
```

The tests mock LLM calls so they can run without network access or real
Gemini credentials.

