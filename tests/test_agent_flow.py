"""Tests for the agent answer flow connecting RAG and repository tools."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent.core import answer_question
from rag.models import RetrievedChunk


class AgentFlowTests(unittest.TestCase):
    def test_answer_uses_retrieval_and_model(self):
        # Prepare fake retrieved chunks
        chunk = RetrievedChunk(file_path="src/auth.py", text="def auth(): pass", score=0.9, metadata={"start_line": 10, "end_line": 12})

        fake_model = SimpleNamespace()
        fake_model.generate = lambda prompt: "FAKE ANSWER"

        with patch("rag.retrieval.retrieve_relevant_chunks", return_value=[chunk]):
            res = answer_question("How authenticate?", embedding_model=None, vector_store=None, model=fake_model, root="/tmp")

        self.assertEqual(res["answer"], "FAKE ANSWER")
        self.assertEqual(len(res["sources"]), 1)
        source = res["sources"][0]
        self.assertEqual(source["file_path"], "src/auth.py")
        self.assertEqual(source["start_line"], 10)
        self.assertEqual(source["end_line"], 12)
        self.assertEqual(source["text"], chunk.text)
        self.assertAlmostEqual(source["score"], 0.9)
        self.assertIn(f"src/auth.py:10-12\n{chunk.text}", res["evidence"])

    def test_answer_extracts_text_from_gemini_content_blocks(self):
        chunk = RetrievedChunk(file_path="rag/retrieval.py", text="def retrieve(): pass", score=0.9, metadata={"start_line": 1, "end_line": 1})
        fake_model = SimpleNamespace()

        def invoke(prompt):
            if prompt.startswith("TOOL_SELECTION:"):
                return "REPO"
            return SimpleNamespace(content=[{"text": "Retrieval is implemented in rag/retrieval.py."}])

        fake_model.invoke = invoke

        with patch("rag.retrieval.retrieve_relevant_chunks", return_value=[chunk]):
            res = answer_question("Which file handles retrieval?", embedding_model=None, vector_store=None, model=fake_model, root="/repo")

        self.assertEqual(res["answer"], "Retrieval is implemented in rag/retrieval.py.")
        self.assertIn("rag/retrieval.py", res["evidence"])
        self.assertEqual(res["sources"][0]["file_path"], "rag/retrieval.py")

    def test_empty_model_response_stays_empty(self):
        chunk = RetrievedChunk(file_path="rag/retrieval.py", text="def retrieve(): pass", score=0.9, metadata={"start_line": 1, "end_line": 1})
        fake_model = SimpleNamespace()

        def generate(prompt):
            if prompt.startswith("TOOL_SELECTION:"):
                return "REPO"
            return SimpleNamespace(content=[])

        fake_model.generate = generate

        with patch("rag.retrieval.retrieve_relevant_chunks", return_value=[chunk]):
            res = answer_question("Which file handles retrieval?", embedding_model=None, vector_store=None, model=fake_model, root="/repo")

        self.assertEqual(res["answer"], "")
        self.assertTrue(res["evidence"])

    def test_answer_model_errors_are_not_hidden(self):
        fake_model = SimpleNamespace()

        def generate(prompt):
            if prompt.startswith("TOOL_SELECTION:"):
                return "REPO"
            raise RuntimeError("Gemini request failed")

        fake_model.generate = generate

        with patch("rag.retrieval.retrieve_relevant_chunks", return_value=[]), patch(
            "agent.mcp_client.search_and_read_repository", return_value=[]
        ):
            with self.assertRaisesRegex(RuntimeError, "Gemini request failed"):
                answer_question("Which file handles retrieval?", embedding_model=None, vector_store=None, model=fake_model, root="/repo")

    def test_answer_falls_back_to_search_and_read(self):
        fake_model = SimpleNamespace()
        fake_model.generate = lambda prompt: "FILE ANSWER"

        with patch("rag.retrieval.retrieve_relevant_chunks", return_value=[]), patch(
            "agent.mcp_client.search_and_read_repository",
            return_value=[("README.md", "Authentication overview\nMore details")],
        ):
            res = answer_question("Where is auth?", embedding_model=None, vector_store=None, model=fake_model, root="/repo")

        self.assertEqual(res["answer"], "FILE ANSWER")
        self.assertEqual(len(res["sources"]), 1)
        self.assertEqual(res["sources"][0]["file_path"], "README.md")

    def test_answer_uses_mcp_server_for_repository_fallback(self):
        fake_model = SimpleNamespace()

        def generate(prompt):
            if prompt.startswith("TOOL_SELECTION:"):
                return "REPO"
            return "MCP ANSWER"

        fake_model.generate = generate

        with tempfile.TemporaryDirectory() as temporary_root:
            repository = Path(temporary_root)
            (repository / "README.md").write_text(
                "mcp repository sentinel\nAdditional details\n", encoding="utf-8"
            )
            with patch("rag.retrieval.retrieve_relevant_chunks", return_value=[]), patch(
                "tools.search_code.search_repository",
                side_effect=AssertionError("direct repository search was used"),
            ), patch(
                "tools.read_file.read_repository_file",
                side_effect=AssertionError("direct repository read was used"),
            ):
                result = answer_question(
                    "mcp repository sentinel",
                    embedding_model=None,
                    vector_store=None,
                    model=fake_model,
                    root=temporary_root,
                )

        self.assertEqual(result["answer"], "MCP ANSWER")
        self.assertEqual(result["sources"][0]["file_path"], "README.md")
        self.assertIn("mcp repository sentinel", result["evidence"])
        self.assertIn("Additional details", result["evidence"])
        self.assertEqual(result["sources"][0]["end_line"], 2)
        self.assertIn("Additional details", result["sources"][0]["text"])


if __name__ == "__main__":
    unittest.main()
