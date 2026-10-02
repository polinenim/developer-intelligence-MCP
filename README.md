```
# Developer Intelligence MCP

A focused repository intelligence project that combines a small MCP server, local repository analysis tools, a repository RAG pipeline, a Gemini-powered AI agent, conversation history, evidence tracking, and web search support through SearXNG.

The system answers questions about a software repository using the repository's actual code as evidence, and the agent can also retrieve external web information via SearXNG when appropriate.

## What the project does

The project provides:

- MCP repository tools to read and search files inside a configured repository root.
- A repository RAG pipeline that scans files, creates text chunks, generates local embeddings, and stores them in PostgreSQL with `pgvector`.
- Semantic retrieval of relevant repository code and documentation.
- A Gemini chat model integrated through LangChain.
- An AI agent that decides whether a question requires repository evidence, web evidence, or both.
- Lightweight in-memory conversation history for follow-up questions.
- Evidence tracking with repository file paths, line ranges, similarity scores, and web result information.
- Web search through a locally running SearXNG instance.
- Unit tests for the repository tools, RAG pipeline, agent, conversation history, and SearXNG integration.

The project is intentionally lightweight and keeps the agent focused on developer and repository intelligence rather than acting as a general-purpose chatbot.

## Architecture

```text
                                                 User
                                                     |
                                                     v
                                            AI Agent
                    (decides: REPO, WEB, or BOTH)
                                                     |
                                    Gemini + LangChain
                                                     |
                            +------------+------------+
                            |                         |
                            v                         v
                Repository Tools           SearXNG Search
                            |                         |
                            v                         v
             Repository RAG                Web Results
                            |                         |
                            +------------+------------+
                                                     |
                                                     v
                                                Evidence
                                                     |
                                                     v
                                                 Gemini
                                                     |
                                                     v
                                    Answer + Sources
```

Repository RAG:

```
Repository
    |
    v
File Scanner
    |
    v
File Filtering
    |
    v
Text Chunking
    |
    v
Sentence Transformers
    |
    v
Local Embeddings
    |
    v
PostgreSQL + pgvector
    |
    v
Similarity Retrieval
```

## Main components

### MCP server
The MCP server exposes repository operations through MCP's stdio transport.

The server provides:

- `read_file(path)` — read a UTF-8 text file by repository-relative path.
- `search_code(query)` — search repository files for a case-insensitive text query.
The implementations are located in:

```
server/mcp_server.py
tools/read_file.py
tools/search_code.py
tools/repository.py
```

The repository root is configured through:

```
REPOSITORY_ROOT
```

Note: The MCP server exposes repository tools for MCP-compatible clients. The internal
agent implementation in this repository reuses the underlying repository tool
functions directly rather than calling the MCP server over the stdio transport.

### Repository RAG
The RAG pipeline provides semantic search over the repository.

It:

1. Scans the configured repository.
2. Filters generated, binary, ignored, and oversized files.
3. Splits source files into text chunks.
4. Keeps file paths and line ranges for each chunk.
5. Generates local embeddings using Sentence Transformers.
6. Stores chunks and embeddings in PostgreSQL with `pgvector`.
7. Retrieves the most relevant chunks for a question.
The embedding model used by the project is:

```
all-MiniLM-L6-v2
```

The RAG implementation is located under:

```
rag/
```

The main components include:

```
rag/filtering.py
rag/scanning.py
rag/chunking.py
rag/embeddings.py
rag/indexing.py
rag/retrieval.py
rag/vector_store.py
```

### Gemini + LangChain
The project uses Gemini as the language model through LangChain.

The integration uses:

```
langchain
langchain-google-genai
```

The Gemini configuration is centralized in:

```
server/llm_config.py
```


The agent obtains the configured model through:

```
agent/agent.py
```

The question-answer flow (decision, retrieval, evidence composition, and prompting) is implemented in:

```
agent/core.py
```

The Gemini API key is supplied through:

```
GEMINI_API_KEY
```

No local large language model is required.

### AI agent
The agent combines repository retrieval, repository tools, web search, and Gemini to answer developer questions.

The agent can decide between:

```
REPO
WEB
BOTH
```

For example:

```
"How does authentication work?"
        |
        v
      REPO
        |
        v
Repository RAG
```

A question such as:

```
"What is the latest Python version?"
```

can use:

```
WEB
 |
 v
SearXNG
```

A question requiring both repository context and external information can use:

```
BOTH
 |
 +--> Repository RAG
 |
 +--> SearXNG
```

The main agent flow is implemented in:

```
agent/core.py
```

### Conversation history
The project includes lightweight in-memory conversation history.

This allows follow-up questions such as:

```
User: How is authentication implemented?

Agent: ...

User: Which file creates the token?

Agent: ...
```

The second question can use the previous conversation context.

Conversation history is:

- stored only in memory
- available during the running process
- cleared when the process restarts
- not stored in PostgreSQL
The implementation is located in:

```
agent/history.py
```

### Evidence
The agent keeps evidence associated with its answers.

Repository evidence can contain:

```
file_path
start_line
end_line
text
score
```

Web evidence can contain:

```
title
url
snippet
```

This allows answers to remain connected to the information used to produce them.

## Web search with SearXNG
The project uses **SearXNG** as its web-search service.

SearXNG acts as a search layer between the AI agent and external web information. It allows the project to perform web searches through a local HTTP service without requiring a paid search API.

The agent decides whether a question needs repository information, web information, or both. SearXNG performs the search, while Gemini uses the retrieved evidence when generating the final answer.

### Why SearXNG
SearXNG was selected because it:

- is open source
- can run locally with Docker
- provides an HTTP search API
- can aggregate results from multiple search engines
- does not require a paid search API for this project
- keeps web search separate from the AI agent
- can be replaced by another search provider later if required
SearXNG is only the search layer. It does not replace Gemini and does not generate the final AI answer.

### SearXNG configuration
The project includes:

```
docker-compose.yml
searxng/settings.yml
```

The Docker Compose configuration runs SearXNG locally and exposes it on:

```
http://localhost:8080
```

The JSON search format is enabled in:

```
searxng/settings.yml
```

### Starting SearXNG
Docker and Docker Compose are required to run a local SearXNG instance.

From the project root:

```
docker compose up -d
```

Check the running service:

```
docker compose ps
```

SearXNG should be available at:

```
http://localhost:8080
```

You can also open the address in a browser to access the SearXNG interface.

### Configure the agent
Set the SearXNG URL in the current PowerShell session:

```
$env:SEARXNG_URL = 'http://localhost:8080'
```

Verify it:

```
echo $env:SEARXNG_URL
```

The Python SearXNG client is implemented in:

```
tools/searxng.py
```

It calls the SearXNG HTTP API and returns search results containing:

```
title
url
snippet
```

### Stopping SearXNG
To stop the local service:

```
docker compose down
```

## Requirements

- Python 3.10 or newer
- PostgreSQL with the `pgvector` extension
- Gemini API key
- Docker and Docker Compose (required only for running the included local SearXNG service)

## Quick setup

### 1. Clone the repository

```
git clone https://github.com/polinenim/developer-intelligence-MCP.git
cd developer-intelligence-MCP
```

### 2. Create and activate the Python environment

```
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install Python dependencies

```
python -m pip install -r requirements.txt
```

### 4. Configure the repository
Set the repository root:

```
$env:REPOSITORY_ROOT = 'C:\path\to\your\repository'
```

### 5. Configure PostgreSQL
Set the database connection:

```
$env:DATABASE_URL = 'postgresql://postgres:postgres@localhost:5432/developer_intelligence'
```

Create the PostgreSQL database and enable the `pgvector` extension (the SQL extension name is `vector`).

Example using the `psql` CLI:

```sh
# create the database (run as a postgres superuser)
psql -c "CREATE DATABASE developer_intelligence;"

# enable the pgvector extension in the new database
psql -d developer_intelligence -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

If you prefer to run SQL inside a psql session:

```sql
CREATE DATABASE developer_intelligence;
\c developer_intelligence
CREATE EXTENSION IF NOT EXISTS vector;
```

After creating the database and extension, set the `DATABASE_URL` environment variable used by this project:

```powershell
$env:DATABASE_URL = 'postgresql://postgres:postgres@localhost:5432/developer_intelligence'
```

### 6. Configure Gemini
Set the Gemini API key:

```
$env:GEMINI_API_KEY = 'your-gemini-api-key'
```

### 7. Start SearXNG

```
docker compose up -d
```

Configure the SearXNG URL:

```
$env:SEARXNG_URL = 'http://localhost:8080'
```

## Index the repository
After configuring the repository and database, run:

```
python -m rag.indexing
```

This scans the configured repository, creates chunks, generates local embeddings, and stores them in PostgreSQL with `pgvector`.

## MCP server
Start the MCP server with:

```
python -m server.mcp_server
```

The MCP server uses stdio transport and exposes the repository tools to an MCP-compatible client.

## Project structure

```
developer-intelligence-mcp/
├── agent/
│   ├── agent.py
│   ├── core.py
│   └── history.py
│
├── rag/
│   ├── __init__.py
│   ├── chunking.py
│   ├── embeddings.py
│   ├── file_filter.py
│   ├── indexing.py
│   ├── models.py
│   ├── retrieval.py
│   ├── scanner.py
│   └── vector_store.py
│
├── server/
│   ├── llm_config.py
│   └── mcp_server.py
│
├── tools/
│   ├── read_file.py
│   ├── repository.py
│   ├── search_code.py
│   └── searxng.py
│
├── tests/
│   ├── test_agent.py
│   ├── test_agent_conversation.py
│   ├── test_agent_flow.py
│   ├── test_agent_web.py
│   ├── test_llm_config.py
│   ├── test_rag.py
│   ├── test_repository_tools.py
│   └── test_searxng.py
│
├── searxng/
│   └── settings.yml
│
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Tests
Run the complete test suite with:

```
python -m unittest discover -s tests -v
```

The tests cover:

- MCP/repository tools
- repository path validation
- RAG chunking
- repository scanning and filtering
- embedding and retrieval behavior
- Gemini configuration
- AI agent flow
- conversation history
- repository/web tool selection
- SearXNG response parsing
The unit tests mock external LLM and HTTP calls where appropriate, so the test suite does not require real Gemini requests or a live web search.

## Example questions
Repository questions:

```
How does authentication work?
```

```
Which function creates the JWT token?
```

```
Which files are responsible for database access?
```

External knowledge questions:

```
What is the latest Python version?
```

```
Who won IPL 2026?
```

Combined questions:

```
Is this project's Python version compatible with the latest Python release?
```

The agent selects the appropriate knowledge source and uses the resulting evidence when generating the answer.