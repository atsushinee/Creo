"""Checkpointer wiring (agent layer keeps the langgraph import, AGENTS.md §2).

One SQLite database backs every conversation memory: the global chat and all
document-chat scopes share it, with per-session threads. Memory now survives
backend restarts.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


@asynccontextmanager
async def open_checkpointer(db_path: str) -> AsyncIterator[AsyncSqliteSaver]:
    """Yield an AsyncSqliteSaver bound to db_path; closed on exit."""
    async with AsyncSqliteSaver.from_conn_string(db_path) as saver:
        yield saver
