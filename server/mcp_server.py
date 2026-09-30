"""Run the repository inspection tools over MCP's stdio transport."""

import os
from pathlib import Path

from mcp.server import MCPServer

from tools.read_file import read_repository_file
from tools.search_code import search_repository


def repository_root() -> Path:
    """Return the repository root configured for this server process."""
    configured_root = os.environ.get("REPOSITORY_ROOT", ".")
    return Path(configured_root).expanduser().resolve()


mcp = MCPServer("developer-intelligence-mcp")


@mcp.tool()
def read_file(path: str) -> str:
    """Read a UTF-8 text file using a path relative to the repository root."""
    return read_repository_file(repository_root(), path)


@mcp.tool()
def search_code(query: str) -> list[str]:
    """Find repository files containing a case-insensitive text query."""
    return search_repository(repository_root(), query)


if __name__ == "__main__":
    mcp.run()
