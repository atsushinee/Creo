"""POST /api/chat — the streaming agent endpoint."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.agent.runtime import AgentRuntime
from app.api.deps import get_agent_runtime, get_session_service
from app.api.sse import encode_sse
from app.core.logging import get_logger
from app.models.chat import ChatRequest
from app.services.session_service import DEFAULT_TITLE, SessionService

router = APIRouter(tags=["chat"])
logger = get_logger("api.chat")

RuntimeDep = Annotated[AgentRuntime, Depends(get_agent_runtime)]
SessionsDep = Annotated[SessionService, Depends(get_session_service)]


@router.post("/chat")
async def chat(
    request: ChatRequest,
    runtime: RuntimeDep,
    sessions: SessionsDep,
) -> StreamingResponse:
    """Run one agent turn and stream Creo Agent Events as SSE (ADR-0003).

    Routes only validate, register the session and encode the stream —
    all agent logic lives in the runtime.
    """
    session = sessions.ensure(request.session_id)
    sessions.touch(session.id, title=request.message if session.title == DEFAULT_TITLE else None)
    logger.info("chat run: session=%s message_len=%d", session.id, len(request.message))
    return StreamingResponse(
        _stream_events(runtime, session.id, request.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_events(
    runtime: AgentRuntime,
    session_id: str,
    message: str,
) -> AsyncIterator[str]:
    async for event in runtime.stream_events(session_id, message):
        yield encode_sse(event)
