"""Creo backend entrypoint: FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.agent.agent import make_agent_builder, make_doc_agent_factory
from app.agent.checkpointer import open_checkpointer
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
from app.services.session_service import SqliteSessionService
from app.services.unstructured_client import UnstructuredClient
from app.tools.knowledge_tools import make_doc_search_tool, make_kb_search_tool

logger = get_logger("main")


def _doc_tool_factory(application: FastAPI) -> Any:
    """Doc-chat tool factory; no tools when the KB stack is disabled."""

    def factory(kb_id: str, doc_id: str) -> list:
        searcher = getattr(application.state, "kb_search_service", None)
        if searcher is None:
            return []
        return [make_doc_search_tool(searcher, kb_id=kb_id, doc_id=doc_id)]

    return factory


def _build_knowledge_stack(application: FastAPI, settings: Settings) -> list:
    """Wire the knowledge-base stack (ADR-0004) onto app.state.

    The registry (SQLite + files + trace + caches) is constructed
    unconditionally and never touches the network; only the remote clients'
    *operations* can fail, per document/request. Returns the extra agent
    tools — an empty list means ingestion/search are unavailable (missing
    config) while the registry stays up.
    """
    knowledge_service = SqliteKnowledgeService(settings.kb_data_dir)
    application.state.knowledge_service = knowledge_service

    interrupted = knowledge_service.fail_interrupted_ingestions()
    if interrupted:
        logger.warning(
            "marked %d in-flight document(s) as failed (backend restarted mid-ingestion)",
            interrupted,
        )

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
        logger.warning(
            "knowledge base ingestion/search disabled, missing config: %s", ", ".join(missing)
        )
        return []

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
    # Lazy connection: constructing this never dials Zilliz; failures surface
    # per operation (failed document / tool error), not as a dead KB stack.
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
    application.state.session_service = SqliteSessionService(settings.data_dir / "sessions.sqlite")
    # Conversation memory (global chat + every doc-chat scope) persists in one
    # SQLite database; threads are isolated by session_id.
    async with open_checkpointer(str(settings.data_dir / "checkpoints.sqlite")) as checkpointer:
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
                checkpointer=checkpointer,
            ),
            # Doc-chat: one scoped graph per (kb_id, doc_id), retrieval filtered
            # to a single document (ADR-0004 Update 3); shared checkpointer.
            doc_agent_builder=make_doc_agent_factory(
                model_provider=settings.model_provider,
                model_name=settings.model_name,
                instructions=settings.agent_instructions,
                model_api_key=settings.model_api_key,
                model_base_url=settings.model_base_url,
                doc_tool_factory=_doc_tool_factory(application),
                checkpointer=checkpointer,
            ),
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
