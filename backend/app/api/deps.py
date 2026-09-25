"""FastAPI dependency getters backed by app.state (singletons per process)."""

from fastapi import Request

from app.agent.runtime import AgentRuntime
from app.services.session_service import SessionService


def get_session_service(request: Request) -> SessionService:
    return request.app.state.session_service


def get_agent_runtime(request: Request) -> AgentRuntime:
    return request.app.state.agent_runtime
