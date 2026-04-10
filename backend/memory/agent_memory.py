"""
Agent Memory — Short-Term Session Memory.

Stores conversation history and agent outputs per session_id (in-memory).
Each session keeps track of the last MAX_HISTORY messages.

In production, swap the dict with Redis using the same interface.
"""
from collections import deque
from datetime import datetime
from typing import Optional
from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)


class AgentMemory:
    """
    Per-session memory store.

    Structure per session:
        {
            "session_id": {
                "messages": deque([{"role": ..., "content": ..., "timestamp": ...}]),
                "task_history": [...],
                "context": {...}
            }
        }
    """

    def __init__(self):
        self._store: dict[str, dict] = {}

    def _get_or_create(self, session_id: str) -> dict:
        """Initialize a session if it doesn't exist yet."""
        if session_id not in self._store:
            self._store[session_id] = {
                "messages": deque(maxlen=settings.MAX_HISTORY),
                "task_history": [],
                "context": {},
                "created_at": datetime.utcnow().isoformat(),
            }
            logger.debug("New memory session created", session_id=session_id)
        return self._store[session_id]

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Append a message to the session's conversation history."""
        session = self._get_or_create(session_id)
        session["messages"].append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def get_messages(self, session_id: str) -> list[dict]:
        """
        Return the conversation history in OpenAI message format.
        Safe to pass directly to llm_client.complete(messages=...).
        """
        session = self._get_or_create(session_id)
        # Return only role + content (not timestamp, which LLM doesn't need)
        return [
            {"role": m["role"], "content": m["content"]}
            for m in session["messages"]
        ]

    def add_task_result(self, session_id: str, task_data: dict) -> None:
        """Save a completed task's results to long-term session history."""
        session = self._get_or_create(session_id)
        session["task_history"].append({
            **task_data,
            "saved_at": datetime.utcnow().isoformat(),
        })

    def set_context(self, session_id: str, key: str, value) -> None:
        """Store arbitrary key-value context (e.g., active namespace, user prefs)."""
        session = self._get_or_create(session_id)
        session["context"][key] = value

    def get_context(self, session_id: str, key: str, default=None):
        """Retrieve a context value."""
        session = self._get_or_create(session_id)
        return session["context"].get(key, default)

    def clear_session(self, session_id: str) -> None:
        """Delete all memory for a session."""
        if session_id in self._store:
            del self._store[session_id]
            logger.info("Memory session cleared", session_id=session_id)

    def get_summary(self, session_id: str) -> dict:
        """Return metadata about a session (for the dashboard)."""
        session = self._get_or_create(session_id)
        return {
            "session_id": session_id,
            "message_count": len(session["messages"]),
            "task_count": len(session["task_history"]),
            "created_at": session["created_at"],
        }

    @property
    def active_sessions(self) -> int:
        return len(self._store)


# ── Global singleton ──────────────────────────────────────────────────────────
agent_memory = AgentMemory()
