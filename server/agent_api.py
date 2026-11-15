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
import os
from flask import Flask, request, jsonify

from rag.embeddings import LocalSentenceTransformerEmbeddings
from rag.vector_store import PostgresVectorStore
from agent.agent import Agent

logger = logging.getLogger(__name__)

MAX_QUESTION_LENGTH = 4000
MAX_CONVERSATION_ID_LENGTH = 128
MAX_REQUEST_BYTES = 64 * 1024


def create_app() -> Flask:
    """Create and configure the Flask app and a single Agent instance.

    The Agent is constructed once at startup using the project's real
    embedding and vector-store classes. Tests should monkeypatch the
    imported classes (`LocalSentenceTransformerEmbeddings`,
    `PostgresVectorStore`, and `get_agent_model`) before calling
    `create_app()` so they can provide lightweight fakes.
    """
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES

    @app.errorhandler(413)
    def request_too_large(error):
        logger.warning("Rejected oversized request: %s", error)
        return jsonify({"error": "request body is too large"}), 413

    database_url = os.environ.get("DATABASE_URL", "")

    # Create real components — tests will monkeypatch these constructors
    # if they need to avoid heavy dependencies.
    embedding = LocalSentenceTransformerEmbeddings()
    vector_store = PostgresVectorStore(database_url)

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
            agent = Agent(embedding_model=embedding, vector_store=vector_store)
            result = agent.ask(
                question, root=repo_root, conversation_id=conversation_id
            )
        except Exception:
            logger.exception("Agent request failed")
            return jsonify({"error": "Agent request failed"}), 500

        return jsonify(result)

    return app


if __name__ == "__main__":
    app = create_app()
    # Default port chosen to avoid common conflicts; the extension will use this.
    app.run(host="127.0.0.1", port=8765)
