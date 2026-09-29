"""Creo backend entrypoint: FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.agent.agent import make_agent_builder
from app.agent.runtime import AgentRuntime
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import get_logger, setup_logging
from app.services.embedding_client import OpenAIEmbeddingClient
from app.services.ingestion_service import IngestionService
from app.services.kb_search import KbSearchService
from app.services.kb_service import SqliteKnowledgeService
from app.services.kb_vector_store import MilvusVectorStore
from app.services.pipeline_cache import PipelineCache
from app.services.session_service import InMemorySessionService
from app.services.unstructured_client import UnstructuredClient
from app.tools.knowledge_tools import make_kb_search_tool

logger = get_logger("main")


def _build_knowledge_stack(application: FastAPI, settings: Settings) -> list:
    """Wire the knowledge-base stack (ADR-0004) onto app.state.

    Returns the extra agent tools; an empty list means the KB stays disabled
    (config missing or an endpoint unreachable) while the rest of Creo runs.
    """
    missing = [
        name
        for name, value in (
            ("CREO_MILVUS_URI", settings.milvus_uri),
            ("CREO_UNSTRUCTURED_API_KEY", settings.unstructured_api_key),
            ("CREO_KB_EMBEDDING_BASE_URL", settings.kb_embedding_base_url),
        )
        if not value
    ]
    if missing:
        logger.warning("knowledge base disabled, missing config: %s", ", ".join(missing))
        return []

    knowledge_service = SqliteKnowledgeService(settings.kb_data_dir)
    unstructured = UnstructuredClient(
        settings.unstructured_api_key,
        server_url=settings.unstructured_server_url,
        profile=settings.unstructured_profile,
        timeout_seconds=settings.unstructured_timeout_seconds,
    )
    embeddings = OpenAIEmbeddingClient(
        settings.kb_embedding_base_url,
        api_key=settings.kb_embedding_api_key,
        model=settings.kb_embedding_model,
    )
    vector_store = MilvusVectorStore(
        settings.milvus_uri,
        token=settings.milvus_token,
        dim=settings.kb_embedding_dim,
        analyzer=settings.kb_analyzer,
    )
    search_service = KbSearchService(knowledge_service, embeddings, vector_store)
    # Content-addressed cache for paid stages: a failed re-run or a
    # re-upload of the same file never re-spends API quota (ADR-0004).
    pipeline_cache = PipelineCache(settings.kb_data_dir / "_cache")

    application.state.knowledge_service = knowledge_service
    application.state.ingestion_service = IngestionService(
        knowledge_service,
        unstructured,
        embeddings,
        vector_store,
        max_chars=settings.kb_chunk_max_characters,
        cache=pipeline_cache,
        parse_profile=settings.unstructured_profile,
        embedding_model=settings.kb_embedding_model,
        embedding_dim=settings.kb_embedding_dim,
    )
    application.state.kb_search_service = search_service
    application.state.vector_store_service = vector_store
    logger.info(
        "knowledge base stack ready (milvus=%s, embedding=%s, analyzer=%s)",
        settings.milvus_uri,
        settings.kb_embedding_model,
        settings.kb_analyzer,
    )
    return [make_kb_search_tool(search_service, default_top_k=settings.kb_search_top_k)]


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    application.state.session_service = InMemorySessionService()
    extra_tools: list = []
    if settings.kb_enabled:
        try:
            extra_tools = _build_knowledge_stack(application, settings)
        except Exception as exc:
            logger.warning("knowledge base disabled (initialization failed: %s)", exc)
    application.state.agent_runtime = AgentRuntime(
        agent_builder=make_agent_builder(
            model_provider=settings.model_provider,
            model_name=settings.model_name,
            instructions=settings.agent_instructions,
            model_api_key=settings.model_api_key,
            model_base_url=settings.model_base_url,
            extra_tools=extra_tools,
        )
    )
    logger.info(
        "Creo backend ready (model=%s, kb=%s)",
        settings.model_display,
        "on" if extra_tools else "off",
    )
    yield
    logger.info("Creo backend shutting down (in-memory state is discarded)")


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)
    application = FastAPI(title="Creo API", version=__version__, lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router, prefix="/api")
    return application


app = create_app()
