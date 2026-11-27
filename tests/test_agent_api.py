import json
import os

import httpx
from langchain_core.exceptions import ModelRateLimitError
from langchain_google_genai.chat_models import GoogleAPIError


def test_ask_endpoint_monkeypatch(monkeypatch, tmp_path):
    # Provide lightweight fakes for heavy dependencies before creating the app
    monkeypatch.setenv("DATABASE_URL", "postgres://unused")
    embedding_warmups = []

    # Fake embedding that avoids importing sentence-transformers
    class FakeEmbedding:
        def embed_documents(self, texts):
            return [[0.0] * 8 for _ in texts]

        def embed_query(self, query: str):
            embedding_warmups.append(query)
            return [0.0] * 8

    # Fake PostgresVectorStore that does not try to connect
    class FakeVectorStore:
        def __init__(self, database_url: str):
            self.database_url = database_url

        def search(self, repository_path: str, query_embedding, limit: int = 5):
            return []

    import rag.embeddings as embeddings_mod
    import rag.vector_store as vector_store_mod
    import agent.agent as agent_mod

    monkeypatch.setattr(embeddings_mod, "LocalSentenceTransformerEmbeddings", FakeEmbedding)
    monkeypatch.setattr(vector_store_mod, "PostgresVectorStore", FakeVectorStore)

    # Ensure the model creation doesn't require an actual API key by stubbing
    def fake_get_agent_model(api_key=None, model_name=None):
        return lambda prompt: ""

    monkeypatch.setattr(agent_mod, "get_agent_model", fake_get_agent_model)

    # Monkeypatch Agent.ask to return a deterministic payload. Do this before
    # creating the app so the constructed Agent uses the patched method.
    asked_roots = []
    asked_conversations = []
    configured_history_stores = []

    def fake_ask(self, question, limit=5, root=None, conversation_id=None):
        asked_roots.append(root)
        asked_conversations.append(conversation_id)
        configured_history_stores.append(self.history_store)
        if question == "trigger error":
            raise RuntimeError("internal detail")
        if question == "trigger rate limit":
            raise ModelRateLimitError("quota exceeded; sensitive provider details")
        if question == "trigger timeout":
            raise httpx.ReadTimeout("sensitive provider details")
        if question == "trigger provider deadline":
            raise GoogleAPIError(
                code=504,
                response_json={"error": {"message": "sensitive provider details"}},
            )
        if question == "invalid agent response":
            return {"answer": [], "sources": [], "evidence": ""}
        if question == "unserializable agent response":
            return {
                "answer": "answer",
                "sources": [{"bad_value": object()}],
                "evidence": "",
            }
        if question == "empty agent answer":
            return {"answer": "", "sources": [], "evidence": "", "source_errors": []}
        source_text = "def run(): pass"
        return {
            "answer": f"answered: {question}",
            "sources": [
                {
                    "file_path": "src/example.py",
                    "start_line": 1,
                    "end_line": 1,
                    "text": source_text,
                    "score": 0.9,
                }
            ],
            "evidence": f"src/example.py:1-1\n{source_text}",
        }

    monkeypatch.setattr(agent_mod.Agent, "ask", fake_ask)

    from server import agent_api

    monkeypatch.setattr(agent_api, "PROJECT_ENV_FILE", tmp_path / "missing.env")
    app = agent_api.create_app()
    client = app.test_client()
    assert embedding_warmups == ["API startup warmup"]

    resp = client.post("/ask", data=json.dumps({"question": "hello"}), content_type="application/json")
    assert resp.status_code == 200
    assert resp.is_json
    data = resp.get_json()
    assert data == {
        "answer": "answered: hello",
        "sources": [
            {
                "file_path": "src/example.py",
                "start_line": 1,
                "end_line": 1,
                "text": "def run(): pass",
                "score": 0.9,
            }
        ],
        "evidence": "src/example.py:1-1\ndef run(): pass",
    }
    assert asked_roots == [None]
    assert asked_conversations == [None]
    assert configured_history_stores[0] is not None

    empty_answer_resp = client.post(
        "/ask",
        data=json.dumps({"question": "empty agent answer"}),
        content_type="application/json",
    )
    assert empty_answer_resp.status_code == 200
    assert empty_answer_resp.get_json() == {
        "answer": "",
        "sources": [],
        "evidence": "",
        "source_errors": [],
    }

    for invalid_response_question in (
        "invalid agent response",
        "unserializable agent response",
    ):
        invalid_response = client.post(
            "/ask",
            data=json.dumps({"question": invalid_response_question}),
            content_type="application/json",
        )
        assert invalid_response.status_code == 502
        assert invalid_response.get_json() == {
            "error": "Agent returned an invalid response"
        }
        assert "bad_value" not in invalid_response.get_data(as_text=True)

    monkeypatch.setenv("REPOSITORY_ROOT", "configured-default")
    workspace_resp = client.post(
        "/ask",
        data=json.dumps(
            {
                "question": "hello",
                "repository_root": str(tmp_path),
                "conversation_id": "workspace-session",
            }
        ),
        content_type="application/json",
    )
    assert workspace_resp.status_code == 200
    assert asked_roots[-1] == str(tmp_path.resolve())
    assert asked_conversations[-1] == "workspace-session"
    assert os.environ["REPOSITORY_ROOT"] == "configured-default"

    for invalid_root in ("", "   ", 42, [], str(tmp_path / "missing")):
        invalid_resp = client.post(
            "/ask",
            data=json.dumps({"question": "hello", "repository_root": invalid_root}),
            content_type="application/json",
        )
        assert invalid_resp.status_code == 400

    file_root = tmp_path / "file.txt"
    file_root.touch()
    invalid_root_resp = client.post(
        "/ask",
        data=json.dumps({"question": "hello", "repository_root": str(file_root)}),
        content_type="application/json",
    )
    assert invalid_root_resp.status_code == 400

    long_question_resp = client.post(
        "/ask",
        data=json.dumps({"question": "x" * 4001}),
        content_type="application/json",
    )
    assert long_question_resp.status_code == 400
    oversized_resp = client.post(
        "/ask",
        data=json.dumps({"question": "x" * (64 * 1024)}),
        content_type="application/json",
    )
    assert oversized_resp.status_code == 413

    for invalid_conversation_id in ("", "  ", 42, "x" * 129):
        invalid_id_resp = client.post(
            "/ask",
            data=json.dumps(
                {"question": "hello", "conversation_id": invalid_conversation_id}
            ),
            content_type="application/json",
        )
        assert invalid_id_resp.status_code == 400

    failed_resp = client.post(
        "/ask",
        data=json.dumps({"question": "trigger error"}),
        content_type="application/json",
    )
    assert failed_resp.status_code == 500
    assert failed_resp.get_json() == {"error": "Agent request failed"}
    assert "internal detail" not in failed_resp.get_data(as_text=True)

    rate_limited_resp = client.post(
        "/ask",
        data=json.dumps({"question": "trigger rate limit"}),
        content_type="application/json",
    )
    assert rate_limited_resp.status_code == 429
    assert rate_limited_resp.get_json() == {
        "error": (
            "Gemini API rate limit or quota has been reached. "
            "Check the configured project's quota or billing and try again later."
        )
    }
    assert "sensitive provider details" not in rate_limited_resp.get_data(as_text=True)

    timed_out_resp = client.post(
        "/ask",
        data=json.dumps({"question": "trigger timeout"}),
        content_type="application/json",
    )
    assert timed_out_resp.status_code == 504
    assert timed_out_resp.get_json() == {
        "error": (
            f"Gemini did not respond within "
            f"{agent_api.GEMINI_REQUEST_TIMEOUT_SECONDS} seconds. "
            "Check network access and try again."
        )
    }
    assert "sensitive provider details" not in timed_out_resp.get_data(as_text=True)

    provider_deadline_resp = client.post(
        "/ask",
        data=json.dumps({"question": "trigger provider deadline"}),
        content_type="application/json",
    )
    assert provider_deadline_resp.status_code == 504
    assert provider_deadline_resp.get_json() == {
        "error": (
            "Gemini's deadline expired before it could complete "
            "the request. Please try again."
        )
    }
    assert "sensitive provider details" not in provider_deadline_resp.get_data(as_text=True)

    for invalid_question in ("", "   ", None, 42):
        invalid_resp = client.post(
            "/ask",
            data=json.dumps({"question": invalid_question}),
            content_type="application/json",
        )
        assert invalid_resp.status_code == 400

    for invalid_root in ("", "   ", 42, []):
        invalid_resp = client.post(
            "/ask",
            data=json.dumps({"question": "hello", "repository_root": invalid_root}),
            content_type="application/json",
        )
        assert invalid_resp.status_code == 400
        assert invalid_resp.get_json() == {
            "error": "repository_root must be a non-empty string"
        }

    malformed_resp = client.post("/ask", data="{", content_type="application/json")
    assert malformed_resp.status_code == 400
    assert malformed_resp.get_json() == {"error": "question is required"}


def test_shell_environment_takes_precedence_over_project_env(monkeypatch, tmp_path):
    from server import agent_api

    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql://postgres:test@127.0.0.1:5433/developer_intelligence\n"
        "GEMINI_API_KEY=file-gemini-key\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(agent_api, "PROJECT_ENV_FILE", env_file)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://postgres:old@localhost:5432/developer_intelligence",
    )
    monkeypatch.setenv("GEMINI_API_KEY", "stale-gemini-key")

    agent_api._load_project_env()

    assert os.environ["DATABASE_URL"] == (
        "postgresql://postgres:old@localhost:5432/developer_intelligence"
    )
    assert os.environ["GEMINI_API_KEY"] == "stale-gemini-key"


def test_create_app_uses_database_url_from_project_env(monkeypatch, tmp_path):
    from server import agent_api

    database_url = (
        "postgresql://postgres:test@127.0.0.1:5433/developer_intelligence"
    )
    env_file = tmp_path / ".env"
    env_file.write_text(f"DATABASE_URL={database_url}\n", encoding="utf-8")
    monkeypatch.setattr(agent_api, "PROJECT_ENV_FILE", env_file)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    configured_urls = {}

    class FakeEmbedding:
        def embed_query(self, query):
            return [0.0]

    class FakeStore:
        def __init__(self, value):
            configured_urls["vector_store"] = value

    class FakeHistoryStore:
        def __init__(self, value):
            configured_urls["history_store"] = value

    monkeypatch.setattr(agent_api, "LocalSentenceTransformerEmbeddings", FakeEmbedding)
    monkeypatch.setattr(agent_api, "PostgresVectorStore", FakeStore)
    monkeypatch.setattr(agent_api, "PostgresConversationHistory", FakeHistoryStore)

    agent_api.create_app()

    assert configured_urls == {
        "vector_store": database_url,
        "history_store": database_url,
    }
