"""Simple in-memory conversation history for the running agent session.

This module provides a tiny append-only history that lives in-process.
It is intentionally simple: stored in a list, resettable for tests, and
not persisted to any external database.
"""
from __future__ import annotations

from collections import deque
from collections import OrderedDict
from threading import RLock
from typing import Any, Deque, Dict, List

MAX_HISTORY_TURNS = 10
MAX_CONVERSATIONS = 256
DEFAULT_CONVERSATION_ID = "default"

_HISTORIES: OrderedDict[str, Deque[Dict[str, Any]]] = OrderedDict()
_LOCK = RLock()


def get_history(
    conversation_id: str | None = DEFAULT_CONVERSATION_ID,
) -> List[Dict[str, Any]]:
    """Return the current conversation history as a list of turns.

    Each turn is a dict with keys: `user`, `assistant`, `sources`.
    """
    if conversation_id is None:
        return []

    with _LOCK:
        history = _HISTORIES.get(conversation_id)
        if history is None:
            return []
        _HISTORIES.move_to_end(conversation_id)
        return list(history)


def append_turn(
    user: str,
    assistant: str,
    sources: List[Dict[str, Any]],
    conversation_id: str | None = DEFAULT_CONVERSATION_ID,
) -> None:
    if conversation_id is None:
        return

    with _LOCK:
        history = _HISTORIES.get(conversation_id)
        if history is None:
            history = deque(maxlen=MAX_HISTORY_TURNS)
            _HISTORIES[conversation_id] = history
        history.append({"user": user, "assistant": assistant, "sources": sources})
        _HISTORIES.move_to_end(conversation_id)
        while len(_HISTORIES) > MAX_CONVERSATIONS:
            _HISTORIES.popitem(last=False)


def clear_history() -> None:
    """Clear in-memory history (useful for tests)."""
    with _LOCK:
        _HISTORIES.clear()
