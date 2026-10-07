"""Simple LLM configuration for Gemini via LangChain.

This module exposes helpers to load the Gemini API key from the environment
and to produce a LangChain `ChatGoogleGenerativeAI` chat-model instance. It does
not perform network requests during model construction.
"""
from __future__ import annotations

import os
from typing import Any, Optional

# Import the LangChain Google GenAI chat model integration.
from langchain_google_genai import ChatGoogleGenerativeAI

ENV_VAR = "GEMINI_API_KEY"


def get_gemini_api_key() -> str:
    """Return the Gemini API key from the environment.

    Raises EnvironmentError when the key is not set.
    """
    key = os.getenv(ENV_VAR)
    if not key:
        raise EnvironmentError(f"{ENV_VAR} not set")
    return key


def init_gemini_chat_model(api_key: Optional[str] = None, model_name: str = "gemini-3.6-flash") -> Any:
    """Initialize and return the LangChain `ChatGoogleGenerativeAI` model.

    - Reads the API key from `GEMINI_API_KEY` when `api_key` is None.
    - Sets `GOOGLE_API_KEY` so the Google Generative AI client can authenticate.
    - Instantiates and returns `ChatGoogleGenerativeAI` without making network calls.
    """
    if api_key is None:
        api_key = get_gemini_api_key()

    # LangChain's Google Gemini chat model relies on the google generative
    # client reading credentials from environment variables. Set the
    # conventional variable used by the client and then construct the model.
    os.environ.setdefault("GOOGLE_API_KEY", api_key)

    # Instantiate and return the LangChain Google GenAI chat model.
    # Pass the API key explicitly via the environment variable and use the
    # provided model name. Construction does not perform network requests.
    return ChatGoogleGenerativeAI(model=model_name)
