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
        self.assertEqual(model.max_retries, 1)
        self.assertEqual(
            model.timeout, llm_config.GEMINI_REQUEST_TIMEOUT_SECONDS
        )
        self.assertGreaterEqual(llm_config.GEMINI_REQUEST_TIMEOUT_SECONDS, 10)

    def test_gemini_key_replaces_stale_google_api_key(self) -> None:
        original_gemini_key = os.environ.get("GEMINI_API_KEY")
        original_google_key = os.environ.get("GOOGLE_API_KEY")
        try:
            os.environ["GEMINI_API_KEY"] = "current-gemini-test-key"
            os.environ["GOOGLE_API_KEY"] = "stale-google-test-key"

            llm_config.init_gemini_chat_model()

            self.assertEqual(
                os.environ["GOOGLE_API_KEY"], "current-gemini-test-key"
            )
        finally:
            if original_gemini_key is None:
                os.environ.pop("GEMINI_API_KEY", None)
            else:
                os.environ["GEMINI_API_KEY"] = original_gemini_key
            if original_google_key is None:
                os.environ.pop("GOOGLE_API_KEY", None)
            else:
                os.environ["GOOGLE_API_KEY"] = original_google_key


if __name__ == "__main__":
    unittest.main()
