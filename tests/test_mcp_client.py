"""Tests for the stdio MCP repository client."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from agent.mcp_client import MCPClientError, search_and_read_repository


class AsyncContext:
    def __init__(self, value):
        self.value = value
        self.exit_arguments = None

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exception_type, exception, traceback):
        self.exit_arguments = (exception_type, exception, traceback)
        return False


def result(*texts, is_error=False):
    return SimpleNamespace(
        is_error=is_error,
        content=[SimpleNamespace(text=text) for text in texts],
    )


class MCPClientTests(unittest.TestCase):
    def setUp(self):
        self.transport_context = AsyncContext((object(), object()))
        self.session = SimpleNamespace(
            initialize=AsyncMock(),
            list_tools=AsyncMock(
                return_value=SimpleNamespace(
                    tools=[
                        SimpleNamespace(name="read_file"),
                        SimpleNamespace(name="search_code"),
                    ]
                )
            ),
            call_tool=AsyncMock(),
        )
        self.session_context = AsyncContext(self.session)

    def test_discovers_invokes_and_cleans_up(self):
        self.session.call_tool.side_effect = [
            result("README.md", "src/main.py"),
            result("README first line\nMore details"),
            result("main first line"),
        ]

        with patch(
            "agent.mcp_client.stdio_client", return_value=self.transport_context
        ) as stdio_client, patch(
            "agent.mcp_client.ClientSession", return_value=self.session_context
        ):
            files = search_and_read_repository("/repo", "query", limit=2)

        self.assertEqual(
            files,
            [
                ("README.md", "README first line\nMore details"),
                ("src/main.py", "main first line"),
            ],
        )
        self.session.initialize.assert_awaited_once()
        self.session.list_tools.assert_awaited_once()
        self.assertEqual(self.session.call_tool.await_count, 3)
        self.assertEqual(
            self.session.call_tool.await_args_list[0].args,
            ("search_code", {"query": "query"}),
        )
        self.assertEqual(
            self.session.call_tool.await_args_list[1].args,
            ("read_file", {"path": "README.md"}),
        )
        parameters = stdio_client.call_args.args[0]
        self.assertEqual(parameters.command, sys.executable)
        self.assertEqual(parameters.env["REPOSITORY_ROOT"], str(Path("/repo").resolve()))
        self.assertNotIn("GEMINI_API_KEY", parameters.env)
        self.assertNotIn("GOOGLE_API_KEY", parameters.env)
        self.assertNotIn("DATABASE_URL", parameters.env)
        self.assertIsNone(self.transport_context.exit_arguments[0])
        self.assertIsNone(self.session_context.exit_arguments[0])

    def test_missing_tool_is_reported_and_contexts_close(self):
        self.session.list_tools.return_value = SimpleNamespace(
            tools=[SimpleNamespace(name="search_code")]
        )

        with patch(
            "agent.mcp_client.stdio_client", return_value=self.transport_context
        ), patch(
            "agent.mcp_client.ClientSession", return_value=self.session_context
        ):
            with self.assertRaisesRegex(MCPClientError, "read_file"):
                search_and_read_repository("/repo", "query")

        self.assertEqual(self.session.call_tool.await_count, 0)
        self.assertIsNotNone(self.transport_context.exit_arguments[0])
        self.assertIsNotNone(self.session_context.exit_arguments[0])

    def test_tool_error_is_reported_without_echoing_tool_output_and_closes(self):
        self.session.call_tool.return_value = result(
            "sensitive repository text", is_error=True
        )

        with patch(
            "agent.mcp_client.stdio_client", return_value=self.transport_context
        ), patch(
            "agent.mcp_client.ClientSession", return_value=self.session_context
        ):
            with self.assertRaises(MCPClientError) as raised:
                search_and_read_repository("/repo", "query")

        self.assertIn("search_code", str(raised.exception))
        self.assertNotIn("sensitive repository text", str(raised.exception))
        self.assertIsNotNone(self.transport_context.exit_arguments[0])
        self.assertIsNotNone(self.session_context.exit_arguments[0])

    def test_connection_failure_is_reported(self):
        with patch("agent.mcp_client.stdio_client", side_effect=OSError("offline")):
            with self.assertRaisesRegex(MCPClientError, "OSError"):
                search_and_read_repository("/repo", "query")


if __name__ == "__main__":
    unittest.main()