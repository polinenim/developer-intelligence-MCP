"""Tests for the minimal agent foundation."""
import os
import unittest

from agent import agent as agent_module
from langchain_google_genai import ChatGoogleGenerativeAI


class AgentTests(unittest.TestCase):
    def test_get_agent_model_constructs_model(self) -> None:
        # Provide a dummy API key to avoid relying on external secrets.
        old_gemini = os.environ.get("GEMINI_API_KEY")
        old_google = os.environ.get("GOOGLE_API_KEY")
        try:
            os.environ["GEMINI_API_KEY"] = "dummy-key"
            # Ensure GOOGLE_API_KEY is not pre-set so the init call will set it.
            if "GOOGLE_API_KEY" in os.environ:
                del os.environ["GOOGLE_API_KEY"]

            model = agent_module.get_agent_model()
            self.assertIsNotNone(model)
            self.assertIsInstance(model, ChatGoogleGenerativeAI)
        finally:
            # Restore environment to avoid leaking state between tests.
            if old_gemini is None:
                os.environ.pop("GEMINI_API_KEY", None)
            else:
                os.environ["GEMINI_API_KEY"] = old_gemini
            if old_google is None:
                os.environ.pop("GOOGLE_API_KEY", None)
            else:
                os.environ["GOOGLE_API_KEY"] = old_google


if __name__ == "__main__":
    unittest.main()
