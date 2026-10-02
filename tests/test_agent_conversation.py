"""Tests for in-memory conversation history and follow-up behavior."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agent import core as agent_core
from agent import history as conv_history
from rag.models import RetrievedChunk


class ConversationTests(unittest.TestCase):
    def setUp(self) -> None:
        conv_history.clear_history()

    def test_empty_history_and_normal_question(self):
        fake_model = SimpleNamespace()
        captured = {}

        def generate(prompt):
            captured['prompt'] = prompt
            return "NORMAL ANSWER"

        fake_model.generate = generate

        chunk = RetrievedChunk(file_path="auth/token.py", text="create_token()", score=0.95, metadata={"start_line": 1, "end_line": 5})
        with patch("rag.retrieval.retrieve_relevant_chunks", return_value=[chunk]):
            res = agent_core.answer_question("Where is token created?", embedding_model=None, vector_store=None, model=fake_model, root="/repo")

        self.assertEqual(res['answer'], "NORMAL ANSWER")
        self.assertTrue('Evidence' in captured['prompt'])
        self.assertEqual(len(res['sources']), 1)
        src = res['sources'][0]
        self.assertEqual(src['file_path'], "auth/token.py")
        self.assertEqual(src['start_line'], 1)
        self.assertEqual(src['end_line'], 5)
        self.assertEqual(src['text'], "create_token()")
        self.assertAlmostEqual(src['score'], 0.95)

    def test_conversation_and_follow_up(self):
        fake_model1 = SimpleNamespace()
        prompts = []

        def gen1(prompt):
            prompts.append(prompt)
            return "ANSWER ONE"

        fake_model1.generate = gen1

        chunk1 = RetrievedChunk(file_path="auth/jwt.py", text="issue_token()", score=0.9, metadata={"start_line": 10, "end_line": 20})
        with patch("rag.retrieval.retrieve_relevant_chunks", return_value=[chunk1]):
            r1 = agent_core.answer_question("How does authentication work?", embedding_model=None, vector_store=None, model=fake_model1, root="/repo")

        # History should now contain one turn
        hist = conv_history.get_history()
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]['user'], "How does authentication work?")
        self.assertEqual(hist[0]['assistant'], "ANSWER ONE")
        self.assertEqual(hist[0]['sources'][0]['file_path'], "auth/jwt.py")

        # Now ask a follow-up using a short reference; ensure history is included in prompt
        fake_model2 = SimpleNamespace()

        def gen2(prompt):
            prompts.append(prompt)
            return "ANSWER TWO"

        fake_model2.generate = gen2
        chunk2 = RetrievedChunk(file_path="auth/token.py", text="create_token()", score=0.85, metadata={"start_line": 1, "end_line": 4})
        with patch("rag.retrieval.retrieve_relevant_chunks", return_value=[chunk2]):
            r2 = agent_core.answer_question("Where is the token created?", embedding_model=None, vector_store=None, model=fake_model2, root="/repo")

        # Ensure prompt for second call contains the first question and answer
        self.assertTrue(any("How does authentication work?" in p and "ANSWER ONE" in p for p in prompts))
        # Ensure returned sources preserved evidence
        self.assertEqual(len(r2['sources']), 1)
        s = r2['sources'][0]
        self.assertEqual(s['file_path'], "auth/token.py")
        self.assertEqual(s['text'], "create_token()")
        self.assertAlmostEqual(s['score'], 0.85)


if __name__ == "__main__":
    unittest.main()
