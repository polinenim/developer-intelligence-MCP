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


def _decide_tools(question: str, history_block: str, model: Any) -> str:
    """Ask the LLM whether to use repository, web, or both.

    The model is asked to return a single token: REPO, WEB, or BOTH. If the
    model response cannot be interpreted, default to REPO to keep behavior
    conservative and repository-first.
    """
    prompt = (
        "TOOL_SELECTION: Decide which sources are needed to answer the question. "
        "Reply with exactly one of: REPO, WEB, or BOTH. No other text.\n\n"
        f"Conversation History:\n{history_block}\nQuestion: {question}\nSelection:"
    )
    try:
        if hasattr(model, "invoke"):
            resp = model.invoke(prompt)
        elif hasattr(model, "generate"):
            resp = model.generate(prompt)
        else:
            resp = model(prompt)
        if isinstance(resp, str):
            token = resp.strip().upper()
        else:
            token = str(resp).strip().upper()
        if "BOTH" in token:
            return "BOTH"
        if "WEB" in token:
            return "WEB"
        if "REPO" in token:
            return "REPO"
    except Exception:
        pass
    return "REPO"


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
    from tools.searxng import search_web

    # Include recent conversation history to support follow-up questions.
    history = conversation_history.get_history()
    history_block = ""
    if history:
        parts: list[str] = []
        for turn in history:
            parts.append(f"User: {turn['user']}")
            parts.append(f"Assistant: {turn['assistant']}")
        history_block = "\n".join(parts) + "\n\n"

    # Ask the model which tools to use for this question (REPO/WEB/BOTH).
    decision = _decide_tools(question, history_block, model)

    # Based on the decision, consult repository and/or web sources.
    chunks = []
    web_results = []
    if decision in ("REPO", "BOTH"):
        try:
            chunks = retrieve_relevant_chunks(question, embedding_model, vector_store, root=root, limit=limit)
        except Exception:
            chunks = []
    if decision in ("WEB", "BOTH"):
        try:
            search_query = ((history[-1]["user"] + " " + question) if history else question)
            web_results = search_web(search_query, limit=limit)
        except Exception as exc:
            web_results = []

    # Build evidence from retrieved chunks and web results
    evidence_lines = []
    sources = []

    if chunks:
        for c in chunks:
            start = c.metadata.get("start_line")
            end = c.metadata.get("end_line")
            evidence_lines.append(f"{c.file_path}:{start}-{end}\n{c.text}")
            sources.append(
                {"file_path": c.file_path, "start_line": start, "end_line": end, "text": c.text, "score": c.score}
            )
    if web_results:
        for w in web_results:
            title = w.get("title", "")
            url = w.get("url", "")
            snippet = w.get("snippet", "")
            evidence_lines.append(f"[WEB] {title} - {url}\n{snippet}")
            sources.append({"type": "web", "title": title, "url": url, "snippet": snippet})

    # If both are empty, fall back to repository search/read as before
    if not chunks and not web_results:
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

    prompt = (
        "You are an assistant answering questions about a repository. Use the evidence"
        " below to answer concisely. Include file:line ranges for sources.\n\n"
        f"Conversation History:\n{history_block}"
        f"Evidence:\n{evidence}\n\nQuestion: {question}\nAnswer:"
    )

    # Call the model; tests will provide a fake model that returns a string.
    result = None
    try:
        if hasattr(model, "invoke"):
            result = model.invoke(prompt)
        elif hasattr(model, "generate"):
            result = model.generate(prompt)
        else:
            result = model(prompt)
    except Exception:
        result = None

    # Normalize response to text.
    if isinstance(result, str):
        answer_text = result
    elif result is None:
        answer_text = ""
    elif hasattr(result, "content"):
        content = result.content

        if isinstance(content, str):
            answer_text = content
        elif isinstance(content, list):
            answer_text = "\n".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            )
        else:
            answer_text = str(content)
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