"""Session storage boundary.

The interface (SessionService) isolates storage. Two implementations:
- InMemorySessionService — process-local (tests, ephemeral use)
- SqliteSessionService   — stdlib SQLite, survives restarts (default wiring)
"""

import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
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
    """Thread-safe in-memory SessionService (ephemeral)."""

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


_SCHEMA = """
CREATE TABLE IF NOT EXISTS session (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _row_to_session(row: sqlite3.Row) -> Session:
    return Session(
        id=row["id"],
        title=row["title"],
        createdAt=datetime.fromisoformat(row["created_at"]),
        updatedAt=datetime.fromisoformat(row["updated_at"]),
    )


class SqliteSessionService:
    """Thread-safe SQLite SessionService — survives backend restarts."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def ensure(self, session_id: str) -> Session:
        now = _utcnow()
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT * FROM session WHERE id = ?", (session_id,)
            ).fetchone()
            if row is None:
                self._conn.execute(
                    "INSERT INTO session (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (session_id, DEFAULT_TITLE, now.isoformat(), now.isoformat()),
                )
                return Session(id=session_id, createdAt=now, updatedAt=now)
        return _row_to_session(row)

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM session WHERE id = ?", (session_id,)
            ).fetchone()
        return _row_to_session(row) if row is not None else None

    def list(self) -> list[Session]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM session ORDER BY updated_at DESC"
            ).fetchall()
        return [_row_to_session(row) for row in rows]

    def touch(self, session_id: str, *, title: str | None = None) -> Session | None:
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT * FROM session WHERE id = ?", (session_id,)
            ).fetchone()
            if row is None:
                return None
            session = _row_to_session(row)
            session.updatedAt = _utcnow()
            if title and session.title == DEFAULT_TITLE:
                session.title = _derive_title(title)
            self._conn.execute(
                "UPDATE session SET title = ?, updated_at = ? WHERE id = ?",
                (session.title, session.updatedAt.isoformat(), session_id),
            )
        return session

    def delete(self, session_id: str) -> bool:
        with self._lock, self._conn:
            cursor = self._conn.execute("DELETE FROM session WHERE id = ?", (session_id,))
        return cursor.rowcount > 0

    def close(self) -> None:
        self._conn.close()


def _derive_title(message: str, max_length: int = 48) -> str:
    title = " ".join(message.split())
    if len(title) > max_length:
        title = title[: max_length - 1].rstrip() + "…"
    return title or DEFAULT_TITLE


def new_session_id() -> str:
    return uuid4().hex
