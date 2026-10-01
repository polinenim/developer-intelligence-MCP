"""Minimal AI agent foundation using the Gemini LLM configuration.

This module provides a tiny API to obtain a configured chat-model instance
that will be used by higher-level agent code later. It intentionally keeps
behavior minimal: it only constructs the model via the existing
`server.llm_config.init_gemini_chat_model` helper and returns it.
"""
from __future__ import annotations

from typing import Any, Optional

from server.llm_config import init_gemini_chat_model


def get_agent_model(api_key: Optional[str] = None, model_name: str = "gemini-default") -> Any:
    """Return a configured Gemini chat-model instance for agent use.

    - Delegates construction to `init_gemini_chat_model` so configuration
      remains centralized in `server.llm_config`.
    - Does not perform any network requests during construction.
    """
    return init_gemini_chat_model(api_key=api_key, model_name=model_name)
