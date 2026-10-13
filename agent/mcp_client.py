"""Client helpers for invoking the repository MCP server over stdio."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


class MCPClientError(RuntimeError):
    """Raised when the repository MCP server cannot complete a request."""


def _text_blocks(result: Any, tool_name: str) -> list[str]:
    if result.is_error:
        raise MCPClientError(f"MCP tool '{tool_name}' returned an error.")

    return [
        block.text
        for block in result.content
        if isinstance(getattr(block, "text", None), str)
    ]


async def _search_and_read_repository(
    root: Path,
    query: str,
    limit: int,
) -> list[tuple[str, str]]:
    environment = os.environ.copy()
    environment["REPOSITORY_ROOT"] = str(root)
    for variable in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "DATABASE_URL"):
        environment.pop(variable, None)

    project_root = Path(__file__).resolve().parents[1]
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "server.mcp_server"],
        env=environment,
        cwd=str(project_root),
    )

    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            discovery = await session.list_tools()
            available_tools = {tool.name for tool in discovery.tools}
            required_tools = {"read_file", "search_code"}
            missing_tools = required_tools - available_tools
            if missing_tools:
                missing = ", ".join(sorted(missing_tools))
                raise MCPClientError(f"Repository MCP server is missing tool(s): {missing}.")

            search_result = await session.call_tool("search_code", {"query": query})
            paths = _text_blocks(search_result, "search_code")

            files = []
            for path in paths[:limit]:
                read_result = await session.call_tool("read_file", {"path": path})
                contents = _text_blocks(read_result, "read_file")
                files.append((path, "\n".join(contents)))

            return files


def search_and_read_repository(
    root: str | Path | None,
    query: str,
    limit: int = 5,
) -> list[tuple[str, str]]:
    """Search and read repository files through the existing MCP server."""
    repository_root = Path(root).expanduser().resolve() if root else Path.cwd().resolve()
    try:
        return asyncio.run(_search_and_read_repository(repository_root, query, limit))
    except MCPClientError:
        raise
    except Exception as error:
        raise MCPClientError(
            f"Repository MCP request failed ({type(error).__name__})."
        ) from error