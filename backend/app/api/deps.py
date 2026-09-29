"""FastAPI dependency getters backed by app.state (singletons per process).

Knowledge-base services (ADR-0004) are Optional: they are only registered on
app.state when CREO_KB_ENABLED=true and the external endpoints are configured;
routes gate on them with a 503 otherwise.
"""

from typing import Any

from fastapi import Request

from app.agent.runtime import AgentRuntime
from app.services.ingestion_service import IngestionService
from app.services.kb_search import KbSearchService
from app.services.kb_service import KnowledgeService
from app.services.session_service import SessionService


def get_session_service(request: Request) -> SessionService:
    return request.app.state.session_service


def get_agent_runtime(request: Request) -> AgentRuntime:
    return request.app.state.agent_runtime


def get_knowledge_service(request: Request) -> KnowledgeService | None:
    return getattr(request.app.state, "knowledge_service", None)


def get_ingestion_service(request: Request) -> IngestionService | None:
    return getattr(request.app.state, "ingestion_service", None)


def get_kb_search_service(request: Request) -> KbSearchService | None:
    return getattr(request.app.state, "kb_search_service", None)


def get_vector_store_service(request: Request) -> Any:
    """MilvusVectorStore instance when the KB stack is enabled, else None."""
    return getattr(request.app.state, "vector_store_service", None)
