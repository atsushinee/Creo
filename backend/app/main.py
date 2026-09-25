"""Creo backend entrypoint: FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.agent.agent import make_agent_builder
from app.agent.runtime import AgentRuntime
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.services.session_service import InMemorySessionService

logger = get_logger("main")


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    application.state.session_service = InMemorySessionService()
    application.state.agent_runtime = AgentRuntime(
        agent_builder=make_agent_builder(
            model_provider=settings.model_provider,
            model_name=settings.model_name,
            instructions=settings.agent_instructions,
            model_api_key=settings.model_api_key,
            model_base_url=settings.model_base_url,
        )
    )
    logger.info("Creo backend ready (model=%s)", settings.model_display)
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
