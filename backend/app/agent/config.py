"""Agent-layer configuration (model spec + system prompt)."""

from dataclasses import dataclass

from app.core.config import get_settings


@dataclass(frozen=True)
class AgentConfig:
    model_provider: str
    model_name: str
    model_api_key: str = ""
    model_base_url: str = ""
    instructions: str = ""


def load_agent_config() -> AgentConfig:
    settings = get_settings()
    return AgentConfig(
        model_provider=settings.model_provider,
        model_name=settings.model_name,
        model_api_key=settings.model_api_key,
        model_base_url=settings.model_base_url,
        instructions=settings.agent_instructions,
    )
