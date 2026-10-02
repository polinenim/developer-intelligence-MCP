"""Tests for agent behavior when web search is involved."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agent import core as agent_core


class AgentWebTests(unittest.TestCase):
    def test_agent_uses_web_when_no_repo_results(self):
        fake_model = SimpleNamespace()
        def generate(prompt):
            if str(prompt).startswith("TOOL_SELECTION:"):
                return "WEB"
            return "WEB ANSWER"
        fake_model.generate = generate

        web_res = [{"title": "News", "url": "http://news", "snippet": "latest event"}]

        with patch("rag.retrieval.retrieve_relevant_chunks", return_value=[]), patch(
            "tools.searxng.search_web", return_value=web_res
        ):
            res = agent_core.answer_question("Who won?", embedding_model=None, vector_store=None, model=fake_model, root="/repo")

        self.assertEqual(res["answer"], "WEB ANSWER")
        self.assertTrue(any(s.get("type") == "web" for s in res["sources"]))

    def test_agent_uses_repo_only_for_repo_questions(self):
        fake_model = SimpleNamespace()
        def generate(prompt):
            if str(prompt).startswith("TOOL_SELECTION:"):
                return "REPO"
            return "REPO ANSWER"
        fake_model.generate = generate

        from rag.models import RetrievedChunk

        chunk = RetrievedChunk(file_path="lib/x.py", text="doit()", score=0.9, metadata={"start_line": 1, "end_line": 2})

        with patch("rag.retrieval.retrieve_relevant_chunks", return_value=[chunk]), patch(
            "tools.searxng.search_web", return_value=[]
        ):
            res = agent_core.answer_question("How is this repo building?", embedding_model=None, vector_store=None, model=fake_model, root="/repo")

        self.assertEqual(res["answer"], "REPO ANSWER")
        self.assertTrue(any("file_path" in s for s in res["sources"]))

    def test_agent_combined_repo_and_web(self):
        fake_model = SimpleNamespace()
        def generate(prompt):
            if str(prompt).startswith("TOOL_SELECTION:"):
                return "BOTH"
            return "COMBINED"
        fake_model.generate = generate

        from rag.models import RetrievedChunk

        chunk = RetrievedChunk(file_path="lib/x.py", text="doit()", score=0.9, metadata={"start_line": 1, "end_line": 2})
        web_res = [{"title": "Lib v2", "url": "http://lib", "snippet": "v2 released"}]

        # Question contains 'version' so heuristic should also call web search
        with patch("rag.retrieval.retrieve_relevant_chunks", return_value=[chunk]), patch(
            "tools.searxng.search_web", return_value=web_res
        ):
            res = agent_core.answer_question("What is the latest version?", embedding_model=None, vector_store=None, model=fake_model, root="/repo")

        self.assertEqual(res["answer"], "COMBINED")
        # Should include both repo and web sources
        types = {s.get("type") for s in res["sources"] if s.get("type")}
        self.assertIn("web", types)


if __name__ == "__main__":
    unittest.main()
