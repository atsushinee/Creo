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
        agent_builder=make_agent_builder(settings.model, settings.agent_instructions)
    )
    logger.info("Creo backend ready (model=%s)", settings.model)
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
