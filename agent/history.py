"""Simple in-memory conversation history for the running agent session.

This module provides a tiny append-only history that lives in-process.
It is intentionally simple: stored in a list, resettable for tests, and
not persisted to any external database.
"""
from __future__ import annotations

from typing import List, Dict, Any

_HISTORY: List[Dict[str, Any]] = []


def get_history() -> List[Dict[str, Any]]:
    """Return the current conversation history as a list of turns.

    Each turn is a dict with keys: `user`, `assistant`, `sources`.
    """
    return list(_HISTORY)


def append_turn(user: str, assistant: str, sources: List[Dict[str, Any]]) -> None:
    _HISTORY.append({"user": user, "assistant": assistant, "sources": sources})


def clear_history() -> None:
    """Clear in-memory history (useful for tests)."""
    _HISTORY.clear()
