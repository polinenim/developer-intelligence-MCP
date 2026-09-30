# Developer Intelligence MCP

A small MCP server that reads and searches a local source repository.

## Requirements

- Python 3.10 or newer

## Setup

From this directory, create and activate a virtual environment, then install the
single runtime dependency:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run

Set `REPOSITORY_ROOT` to the local repository the MCP host should inspect, then
start the server. If the variable is omitted, the current working directory is
used as the repository root.

```powershell
$env:REPOSITORY_ROOT = 'C:\path\to\your\repository'
python -m server.mcp_server
```

The server uses MCP's stdio transport, so configure your MCP host to launch
`python -m server.mcp_server` with this directory as its working directory and
the `REPOSITORY_ROOT` environment variable set to the target repository.

Both tools accept repository-relative paths or queries. File reads are limited
to UTF-8 text files inside the selected root. Search is case-insensitive, skips
common generated directories and files larger than 1 MB, and returns sorted
repository-relative paths.

## Tools

- `read_file(path)` reads a UTF-8 text file from the repository using its
  repository-relative path.
- `search_code(query)` searches repository code for a case-insensitive word,
  function name, class name, or other text query and returns matching file paths.

## Project Status

Currently includes:

- MCP server
- Repository file reading
- Repository code search
- Basic automated tests

RAG, embeddings, LangChain, and other components will be added later.

## Verify

Run the standard-library checks from this directory:

```powershell
python -m unittest discover -s tests -v
```
