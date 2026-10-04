"""Tests for the small external-facing Agent wrapper class."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agent.agent import Agent
from rag.models import RetrievedChunk


class AgentInterfaceTests(unittest.TestCase):
    def test_agent_ask_uses_provided_model_and_returns_sources(self):
        fake_model = SimpleNamespace()
        fake_model.generate = lambda prompt: "CLASS ANSWER"

        chunk = RetrievedChunk(file_path="lib/x.py", text="doit()", score=0.9, metadata={"start_line": 1, "end_line": 2})

        with patch("rag.retrieval.retrieve_relevant_chunks", return_value=[chunk]):
            agent = Agent(embedding_model=None, vector_store=None, model=fake_model)
            res = agent.ask("How to run?", limit=2)

        self.assertEqual(res["answer"], "CLASS ANSWER")
        self.assertEqual(len(res["sources"]), 1)
        self.assertEqual(res["sources"][0]["file_path"], "lib/x.py")


if __name__ == "__main__":
    unittest.main()
