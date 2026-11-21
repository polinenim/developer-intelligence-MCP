"""Conversation history backed by memory or PostgreSQL.

The module-level helpers preserve the original in-memory behavior. The
PostgreSQL store persists turns for API use without changing callers that do
not configure persistent history.
"""
from __future__ import annotations

import json
from collections import deque
from collections import OrderedDict
from threading import RLock
from typing import Any, Deque, Dict, List, Protocol

MAX_HISTORY_TURNS = 10
MAX_PERSISTED_HISTORY_TURNS = 20
MAX_CONVERSATIONS = 256
DEFAULT_CONVERSATION_ID = "default"

_HISTORIES: OrderedDict[str, Deque[Dict[str, Any]]] = OrderedDict()
_LOCK = RLock()


class HistoryStore(Protocol):
    """Storage interface used by the agent for conversation turns."""

    def get_history(
        self, conversation_id: str | None = DEFAULT_CONVERSATION_ID
    ) -> List[Dict[str, Any]]:
        """Return turns in chronological order."""
        ...

    def append_turn(
        self,
        user: str,
        assistant: str,
        sources: List[Dict[str, Any]],
        conversation_id: str | None = DEFAULT_CONVERSATION_ID,
    ) -> None:
        """Append a turn to one conversation."""
        ...


class PostgresConversationHistory:
    """Persist recent conversation turns in the configured PostgreSQL DB."""

    def __init__(self, database_url: str) -> None:
        if not database_url.strip():
            raise ValueError("database_url must not be empty")
        self.database_url = database_url

    def get_history(
        self, conversation_id: str | None = DEFAULT_CONVERSATION_ID
    ) -> List[Dict[str, Any]]:
        if conversation_id is None:
            return []

        with self._connect() as connection:
            with connection.cursor() as cursor:
                self._ensure_schema(cursor)
                cursor.execute(
                    """
                    SELECT user_message, assistant_message, sources
                    FROM conversation_turns
                    WHERE conversation_id = %s
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (conversation_id, MAX_PERSISTED_HISTORY_TURNS),
                )
                rows = cursor.fetchall()

        turns = []
        for user, assistant, sources in reversed(rows):
            if isinstance(sources, str):
                sources = json.loads(sources)
            turns.append(
                {"user": user, "assistant": assistant, "sources": sources}
            )
        return turns

    def append_turn(
        self,
        user: str,
        assistant: str,
        sources: List[Dict[str, Any]],
        conversation_id: str | None = DEFAULT_CONVERSATION_ID,
    ) -> None:
        if conversation_id is None:
            return

        with self._connect() as connection:
            with connection.cursor() as cursor:
                self._ensure_schema(cursor)
                cursor.execute(
                    """
                    INSERT INTO conversation_turns
                        (conversation_id, user_message, assistant_message, sources)
                    VALUES (%s, %s, %s, %s::jsonb)
                    """,
                    (conversation_id, user, assistant, json.dumps(sources)),
                )
                cursor.execute(
                    """
                    DELETE FROM conversation_turns
                    WHERE conversation_id = %s
                      AND id NOT IN (
                          SELECT id
                          FROM conversation_turns
                          WHERE conversation_id = %s
                          ORDER BY id DESC
                          LIMIT %s
                      )
                    """,
                    (
                        conversation_id,
                        conversation_id,
                        MAX_PERSISTED_HISTORY_TURNS,
                    ),
                )

    @staticmethod
    def _ensure_schema(cursor) -> None:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_turns (
                id BIGSERIAL PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                user_message TEXT NOT NULL,
                assistant_message TEXT NOT NULL,
                sources JSONB NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS conversation_turns_conversation_id_id_idx
            ON conversation_turns (conversation_id, id DESC)
            """
        )

    def _connect(self):
        try:
            from psycopg import connect
        except ImportError as error:
            raise RuntimeError("Install psycopg before using PostgreSQL storage.") from error
        return connect(self.database_url)


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
