"""Tests for the simple Gemini + LangChain configuration module.

These tests verify the environment variable handling and that the
initialization function returns a model-like object without performing any
network requests. The tests do not contact the Gemini service.
"""
import os
import unittest

from server import llm_config
from langchain_google_genai import ChatGoogleGenerativeAI


class LLMConfigTests(unittest.TestCase):
    def test_get_gemini_api_key_missing_raises(self) -> None:
        if "GEMINI_API_KEY" in os.environ:
            del os.environ["GEMINI_API_KEY"]
        with self.assertRaises(EnvironmentError):
            llm_config.get_gemini_api_key()

    def test_init_gemini_chat_model_returns_object(self) -> None:
        # Provide a dummy API key; the call should not perform network I/O.
        os.environ["GEMINI_API_KEY"] = "test-key"
        model = llm_config.init_gemini_chat_model()
        # Model must be a LangChain Google GenAI chat instance and no network
        # I/O should have occurred during construction. Verify the returned
        # type and that the GOOGLE_API_KEY env var was set from GEMINI_API_KEY.
        self.assertIsInstance(model, ChatGoogleGenerativeAI)
        self.assertEqual(os.environ.get("GOOGLE_API_KEY"), "test-key")


if __name__ == "__main__":
    unittest.main()
