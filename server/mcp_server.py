"""Run the repository inspection tools over MCP's stdio transport."""

from mcp.server import MCPServer

from tools.read_file import read_repository_file
from tools.repository import repository_root
from tools.search_code import search_repository


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
