"""Tests for the agent answer flow connecting RAG and repository tools."""
import unittest
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
        self.assertEqual(res["sources"][0]["file_path"], "src/auth.py")

    def test_answer_falls_back_to_search_and_read(self):
        fake_model = SimpleNamespace()
        fake_model.generate = lambda prompt: "FILE ANSWER"

        with patch("rag.retrieval.retrieve_relevant_chunks", return_value=[]), patch(
            "tools.search_code.search_repository", return_value=["README.md"]
        ), patch("tools.read_file.read_repository_file", return_value="Authentication overview\nMore details"):
            res = answer_question("Where is auth?", embedding_model=None, vector_store=None, model=fake_model, root="/repo")

        self.assertEqual(res["answer"], "FILE ANSWER")
        self.assertEqual(len(res["sources"]), 1)
        self.assertEqual(res["sources"][0]["file_path"], "README.md")


if __name__ == "__main__":
    unittest.main()
