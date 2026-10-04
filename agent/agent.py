"""Minimal AI agent foundation using the Gemini LLM configuration.

This module provides a tiny API to obtain a configured chat-model instance
that will be used by higher-level agent code later. It intentionally keeps
behavior minimal: it only constructs the model via the existing
`server.llm_config.init_gemini_chat_model` helper and returns it.
"""

from __future__ import annotations

from typing import Any, Optional

from agent.core import answer_question as _core_answer_question
from server.llm_config import init_gemini_chat_model
from tools.repository import repository_root


def get_agent_model(
    api_key: Optional[str] = None,
    model_name: str = "gemini-default",
) -> Any:
    """Return a configured Gemini chat-model instance for agent use.

    - Delegates construction to `init_gemini_chat_model` so configuration
      remains centralized in `server.llm_config`.
    - Does not perform any network requests during construction.
    """
    return init_gemini_chat_model(
        api_key=api_key,
        model_name=model_name,
    )


def answer_question(
    question: str,
    embedding_model: Any,
    vector_store: Any,
    model: Optional[Any] = None,
    limit: int = 5,
) -> dict:
    """Answer `question` against the repository configured for this process.

    This convenience wrapper uses the server's `REPOSITORY_ROOT` (via
    `tools.repository.repository_root`) so callers don't need to pass the
    repository path explicitly. The heavy lifting is delegated to
    `agent.core.answer_question`.
    """
    root = repository_root()

    return _core_answer_question(
        question,
        embedding_model=embedding_model,
        vector_store=vector_store,
        model=model,
        root=root,
        limit=limit,
    )


class Agent:
    """A minimal, future-friendly agent interface for external callers.

    This small wrapper is intended for use by external integrations
    (for example a VS Code extension). It keeps a configured model,
    embedding model, and vector store and exposes a single `ask()` method.
    """

    def __init__(
        self,
        embedding_model: Any,
        vector_store: Any,
        model: Optional[Any] = None,
        api_key: Optional[str] = None,
        model_name: str = "gemini-default",
    ) -> None:
        self.embedding_model = embedding_model
        self.vector_store = vector_store

        if model is None:
            self.model = get_agent_model(
                api_key=api_key,
                model_name=model_name,
            )
        else:
            self.model = model

    def ask(self, question: str, limit: int = 5) -> dict:
        """Ask the agent a question and return the result dict.

        Result shape matches `agent.core.answer_question`
        (answer, sources, evidence).
        """
        return answer_question(
            question,
            embedding_model=self.embedding_model,
            vector_store=self.vector_store,
            model=self.model,
            limit=limit,
        )