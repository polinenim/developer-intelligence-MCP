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

from typing import Any
import os
from flask import Flask, request, jsonify

from rag.embeddings import LocalSentenceTransformerEmbeddings
from rag.vector_store import PostgresVectorStore
from agent.agent import Agent, get_agent_model


def create_app() -> Flask:
    """Create and configure the Flask app and a single Agent instance.

    The Agent is constructed once at startup using the project's real
    embedding and vector-store classes. Tests should monkeypatch the
    imported classes (`LocalSentenceTransformerEmbeddings`,
    `PostgresVectorStore`, and `get_agent_model`) before calling
    `create_app()` so they can provide lightweight fakes.
    """
    app = Flask(__name__)

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
        data = request.get_json(force=True)
        question = data.get("question") if isinstance(data, dict) else None
        if not question or not isinstance(question, str):
            return jsonify({"error": "question is required"}), 400

        try:
            # Construct Agent per-request to ensure the model instance is
            # freshly created in the request context.
            agent = Agent(embedding_model=embedding, vector_store=vector_store)
            result = agent.ask(question)
        except Exception as exc:  # Keep errors local and return 500
            return jsonify({"error": str(exc)}), 500

        return jsonify(result)

    return app


if __name__ == "__main__":
    app = create_app()
    # Default port chosen to avoid common conflicts; the extension will use this.
    app.run(host="127.0.0.1", port=8765)
