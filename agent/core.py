"""Agent core: simple QA flow connecting RAG and repository tools to the LLM.

This module implements a minimal answer flow:
- retrieve relevant chunks via RAG
- if none, search and read repository files
- compose a short prompt with evidence
- call the provided LLM model (or obtain one)
- return answer text plus simple source metadata

The implementation is intentionally small and avoids any network calls
when tests provide a mocked model.
"""
from __future__ import annotations

from typing import Any, Optional

from server.llm_config import init_gemini_chat_model
from agent import history as conversation_history


def get_agent_model(api_key: Optional[str] = None, model_name: str = "gemini-default") -> Any:
    return init_gemini_chat_model(api_key=api_key, model_name=model_name)


def answer_question(
    question: str,
    embedding_model: Any,
    vector_store: Any,
    model: Optional[Any] = None,
    root: Optional[str] = None,
    limit: int = 5,
) -> dict:
    """Answer `question` using repository RAG and tools.

    Returns: {"answer": str, "sources": list[dict], "evidence": str}
    """
    if model is None:
        model = get_agent_model()

    # Local imports to avoid startup costs and import cycles in tests.
    from rag.retrieval import retrieve_relevant_chunks
    from tools.search_code import search_repository
    from tools.read_file import read_repository_file

    try:
        chunks = retrieve_relevant_chunks(question, embedding_model, vector_store, root=root, limit=limit)
    except Exception:
        chunks = []

    evidence_lines: list[str] = []
    sources: list[dict] = []

    if chunks:
        for c in chunks:
            start = c.metadata.get("start_line")
            end = c.metadata.get("end_line")
            # preserve chunk text and similarity score in the source metadata
            evidence_lines.append(f"{c.file_path}:{start}-{end}\n{c.text}")
            sources.append(
                {
                    "file_path": c.file_path,
                    "start_line": start,
                    "end_line": end,
                    "text": c.text,
                    "score": c.score,
                }
            )
    else:
        try:
            hits = search_repository(root, question)
        except Exception:
            hits = []
        for path in hits[:limit]:
            try:
                content = read_repository_file(root, path)
            except Exception:
                content = ""
            first_line = content.splitlines()[0] if content else ""
            evidence_lines.append(f"{path}:1-1\n{first_line}")
            sources.append({"file_path": path, "start_line": 1, "end_line": 1, "text": first_line, "score": None})

    evidence = "\n\n".join(evidence_lines)

    # Include recent conversation history to support follow-up questions.
    history = conversation_history.get_history()
    history_block = ""
    if history:
        parts: list[str] = []
        for turn in history:
            parts.append(f"User: {turn['user']}")
            parts.append(f"Assistant: {turn['assistant']}")
        history_block = "\n".join(parts) + "\n\n"

    prompt = (
        "You are an assistant answering questions about a repository. Use the evidence"
        " below to answer concisely. Include file:line ranges for sources.\n\n"
        f"Conversation History:\n{history_block}"
        f"Evidence:\n{evidence}\n\nQuestion: {question}\nAnswer:"
    )

    # Call the model; tests will provide a fake model that returns a string.
    result = None
    try:
        if hasattr(model, "generate"):
            result = model.generate(prompt)
        elif hasattr(model, "invoke"):
            result = model.invoke(prompt)
        else:
            result = model(prompt)
    except Exception:
        result = None

    # Normalize response to text.
    if isinstance(result, str):
        answer_text = result
    elif result is None:
        answer_text = ""
    else:
        gens = getattr(result, "generations", None)
        if gens:
            try:
                first = gens[0]
                if isinstance(first, list):
                    answer_text = getattr(first[0], "text", str(first[0]))
                else:
                    answer_text = getattr(first, "text", str(first))
            except Exception:
                answer_text = str(result)
        else:
            answer_text = str(result)

    result_dict = {"answer": answer_text, "sources": sources, "evidence": evidence}

    # Persist the new conversation turn in memory for the running session.
    try:
        conversation_history.append_turn(question, answer_text, sources)
    except Exception:
        # History is best-effort; do not fail the request if saving history fails.
        pass

    return result_dict
