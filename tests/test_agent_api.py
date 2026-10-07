import json
import os


def test_ask_endpoint_monkeypatch(monkeypatch):
    # Provide lightweight fakes for heavy dependencies before creating the app
    monkeypatch.setenv("DATABASE_URL", "postgres://unused")

    # Fake embedding that avoids importing sentence-transformers
    class FakeEmbedding:
        def embed_documents(self, texts):
            return [[0.0] * 8 for _ in texts]

        def embed_query(self, query: str):
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
    def fake_ask(self, question, limit=5):
        return {"answer": f"answered: {question}", "sources": [], "evidence": ""}

    monkeypatch.setattr(agent_mod.Agent, "ask", fake_ask)

    from server.agent_api import create_app

    app = create_app()
    client = app.test_client()

    resp = client.post("/ask", data=json.dumps({"question": "hello"}), content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["answer"] == "answered: hello"
    assert isinstance(data["sources"], list)
