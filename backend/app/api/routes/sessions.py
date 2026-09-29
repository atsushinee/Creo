"""Session management endpoints (list / history / delete)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.agent.runtime import AgentRuntime
from app.api.deps import get_agent_runtime, get_session_service
from app.core.logging import get_logger
from app.models.chat import HistoryMessage, SessionOut
from app.services.session_service import SessionService

router = APIRouter(tags=["sessions"])
logger = get_logger("api.sessions")

RuntimeDep = Annotated[AgentRuntime, Depends(get_agent_runtime)]
SessionsDep = Annotated[SessionService, Depends(get_session_service)]


@router.get("/sessions")
async def list_sessions(sessions: SessionsDep) -> list[SessionOut]:
    return [
        SessionOut(
            id=session.id,
            title=session.title,
            createdAt=session.createdAt.isoformat(),
            updatedAt=session.updatedAt.isoformat(),
        )
        for session in sessions.list()
    ]


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    runtime: RuntimeDep,
    sessions: SessionsDep,
    kb_id: str | None = None,
    doc_id: str | None = None,
) -> list[HistoryMessage]:
    if sessions.get(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")
    doc_scope = (kb_id, doc_id) if kb_id and doc_id else None
    try:
        return await runtime.get_history(session_id, doc_scope=doc_scope)
    except Exception as exc:
        logger.warning("history unavailable for session=%s: %s", session_id, exc)
        raise HTTPException(status_code=503, detail="agent history unavailable") from exc


@router.get("/sessions/{session_id}/trace")
async def get_session_trace(session_id: str, runtime: RuntimeDep) -> list[dict]:
    """Structural run events recorded for this session (tools, timings)."""
    return runtime.get_session_trace(session_id)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str, sessions: SessionsDep) -> None:
    if not sessions.delete(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    # Note: in-process checkpointer state for the thread is dropped with the
    # process; persistent session deletion is a post-MVP concern.
