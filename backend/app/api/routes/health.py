"""GET /api/health — liveness + agent configuration status."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app import __version__
from app.agent.runtime import AgentRuntime
from app.api.deps import get_agent_runtime
from app.core.config import get_settings
from app.models.chat import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(
    runtime: Annotated[AgentRuntime, Depends(get_agent_runtime)],
) -> HealthOut:
    settings = get_settings()
    return HealthOut(
        status="ok",
        version=__version__,
        model=settings.model,
        agent="ready" if runtime.status == "ready" else "pending",
    )
