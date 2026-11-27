"""Minimal local HTTP API exposing the Agent.ask() interface.

This Flask app provides a single endpoint `/ask` which accepts JSON
{"question": "..."} and returns the agent response as JSON. It
creates a single `Agent` at app startup using the project's real
components so the extension can interact with the existing V1/V2 code.

For local demo/test use the environment variable `DATABASE_URL` should
be set to the PostgreSQL connection URL used by `PostgresVectorStore`.
Tests should monkeypatch the heavy dependencies before calling
``create_app()`` so they can run without external services.
"""
from __future__ import annotations

import logging
from pathlib import Path
from flask import Flask, request, jsonify
import httpx
from langchain_core.exceptions import ModelAPIError, ModelRateLimitError, ModelTimeoutError
from server.llm_config import GEMINI_REQUEST_TIMEOUT_SECONDS

from rag.embeddings import LocalSentenceTransformerEmbeddings
from rag.vector_store import PostgresVectorStore
from agent.agent import Agent
from agent.history import PostgresConversationHistory
from tools.environment import load_project_environment, resolve_database_url

logger = logging.getLogger(__name__)

MAX_QUESTION_LENGTH = 4000
MAX_CONVERSATION_ID_LENGTH = 128
MAX_REQUEST_BYTES = 64 * 1024
PROJECT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def _load_project_env() -> None:
    """Load project-local settings without overriding shell configuration."""
    load_project_environment(PROJECT_ENV_FILE)


def _is_valid_agent_response(result: object) -> bool:
    """Check the stable response fields expected from Agent.ask()."""
    if not isinstance(result, dict):
        return False
    if not isinstance(result.get("answer"), str):
        return False
    if not isinstance(result.get("sources"), list):
        return False
    if not isinstance(result.get("evidence"), str):
        return False
    return "source_errors" not in result or isinstance(result["source_errors"], list)


def create_app() -> Flask:
    """Create and configure the Flask app and a single Agent instance.

    The embedding model and vector store are initialized at startup. An
    Agent and its Gemini model are constructed for each request.
    """
    _load_project_env()
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES

    @app.errorhandler(413)
    def request_too_large(error):
        logger.warning("Rejected oversized request: %s", error)
        return jsonify({"error": "request body is too large"}), 413

    database_url = resolve_database_url()

    # Load the local embedding model before accepting requests so a cold
    # Hugging Face download cannot consume the extension's request timeout.
    embedding = LocalSentenceTransformerEmbeddings()
    logger.info("Loading the local embedding model before accepting requests")
    embedding.embed_query("API startup warmup")

    # Create real components — tests will monkeypatch these constructors
    # if they need to avoid heavy dependencies.
    vector_store = PostgresVectorStore(database_url)
    history_store = (
        PostgresConversationHistory(database_url) if database_url.strip() else None
    )

    # NOTE: construct the Agent per-request below instead of reusing a single
    # Agent/model instance created at startup. Some model adapters are not
    # safe to reuse across threads or requests; creating the model on-demand
    # preserves the successful direct `Agent.ask()` behavior while keeping
    # the API simple.


    @app.route("/ask", methods=["POST"])
    def ask():
        data = request.get_json(force=True, silent=True)
        question = data.get("question") if isinstance(data, dict) else None
        if not isinstance(question, str) or not question.strip():
            return jsonify({"error": "question is required"}), 400
        if len(question) > MAX_QUESTION_LENGTH:
            return jsonify(
                {"error": f"question must be at most {MAX_QUESTION_LENGTH} characters"}
            ), 400
        repo_root = data.get("repository_root") if isinstance(data, dict) else None
        if repo_root is not None and (
            not isinstance(repo_root, str) or not repo_root.strip()
        ):
            return jsonify({"error": "repository_root must be a non-empty string"}), 400
        if repo_root is not None:
            try:
                resolved_root = Path(repo_root).expanduser().resolve(strict=True)
            except (OSError, RuntimeError, ValueError):
                return jsonify(
                    {"error": "repository_root must be an existing directory"}
                ), 400
            if not resolved_root.is_dir():
                return jsonify(
                    {"error": "repository_root must be an existing directory"}
                ), 400
            repo_root = str(resolved_root)

        conversation_id = (
            data.get("conversation_id") if isinstance(data, dict) else None
        )
        if conversation_id is not None and (
            not isinstance(conversation_id, str)
            or not conversation_id.strip()
            or len(conversation_id) > MAX_CONVERSATION_ID_LENGTH
        ):
            return jsonify(
                {
                    "error": (
                        "conversation_id must be a non-empty string of at most "
                        f"{MAX_CONVERSATION_ID_LENGTH} characters"
                    )
                }
            ), 400

        try:
            # Construct Agent per-request to ensure the model instance is
            # freshly created in the request context.
            agent = Agent(
                embedding_model=embedding,
                vector_store=vector_store,
                history_store=history_store,
            )
            result = agent.ask(
                question, root=repo_root, conversation_id=conversation_id
            )
        except ModelRateLimitError:
            logger.warning("Gemini API rate limit or quota reached")
            return jsonify(
                {
                    "error": (
                        "Gemini API rate limit or quota has been reached. "
                        "Check the configured project's quota or billing and try again later."
                    )
                }
            ), 429
        except (ModelTimeoutError, httpx.TimeoutException):
            logger.warning("Gemini API request timed out")
            return jsonify(
                {
                    "error": (
                        f"Gemini did not respond within "
                        f"{GEMINI_REQUEST_TIMEOUT_SECONDS} seconds. "
                        "Check network access and try again."
                    )
                }
            ), 504
        except ModelAPIError as error:
            if getattr(error, "code", None) == 504:
                logger.warning("Gemini API deadline expired")
                return jsonify(
                    {
                        "error": (
                            "Gemini's deadline expired before it could complete "
                            "the request. Please try again."
                        )
                    }
                ), 504
            logger.warning(
                "Gemini API returned an upstream error (HTTP %s)",
                getattr(error, "code", "unknown"),
            )
            return jsonify(
                {"error": "Gemini API returned an upstream error. Please try again."}
            ), 502
        except Exception:
            logger.exception("Agent request failed")
            return jsonify({"error": "Agent request failed"}), 500

        if not _is_valid_agent_response(result):
            logger.error("Agent returned a response with an invalid shape")
            return jsonify({"error": "Agent returned an invalid response"}), 502

        try:
            return jsonify(result)
        except (TypeError, ValueError):
            logger.exception("Agent returned a response that could not be serialized")
            return jsonify({"error": "Agent returned an invalid response"}), 502

    return app


if __name__ == "__main__":
    app = create_app()
    # Default port chosen to avoid common conflicts; the extension will use this.
    app.run(host="127.0.0.1", port=8765)
