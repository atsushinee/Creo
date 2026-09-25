"""Session storage boundary.

The interface (SessionService) isolates storage: the current implementation is
in-memory; Redis/PostgreSQL implementations can replace it without touching
routes or the agent runtime (docs/architecture.md §5).
"""

import threading
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from pydantic import BaseModel, Field

DEFAULT_TITLE = "New chat"


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Session(BaseModel):
    id: str
    title: str = DEFAULT_TITLE
    createdAt: datetime = Field(default_factory=_utcnow)
    updatedAt: datetime = Field(default_factory=_utcnow)


class SessionService(Protocol):
    """Storage-agnostic session registry. Message history lives in the agent
    runtime's checkpointer; this service only tracks session metadata."""

    def ensure(self, session_id: str) -> Session: ...
    def get(self, session_id: str) -> Session | None: ...
    def list(self) -> list[Session]: ...
    def touch(self, session_id: str, *, title: str | None = None) -> Session | None: ...
    def delete(self, session_id: str) -> bool: ...


class InMemorySessionService:
    """Thread-safe in-memory SessionService. Swap for Redis/PG later."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def ensure(self, session_id: str) -> Session:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = Session(id=session_id)
                self._sessions[session_id] = session
            return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            return self._sessions.get(session_id)

    def list(self) -> list[Session]:
        with self._lock:
            return sorted(self._sessions.values(), key=lambda s: s.updatedAt, reverse=True)

    def touch(self, session_id: str, *, title: str | None = None) -> Session | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            session.updatedAt = _utcnow()
            if title and session.title == DEFAULT_TITLE:
                session.title = _derive_title(title)
            return session

    def delete(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None


def _derive_title(message: str, max_length: int = 48) -> str:
    title = " ".join(message.split())
    if len(title) > max_length:
        title = title[: max_length - 1].rstrip() + "…"
    return title or DEFAULT_TITLE


def new_session_id() -> str:
    return uuid4().hex
