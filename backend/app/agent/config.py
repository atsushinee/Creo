"""Agent-layer configuration (model spec + system prompt)."""

from dataclasses import dataclass

from app.core.config import get_settings


@dataclass(frozen=True)
class AgentConfig:
    model_spec: str
    instructions: str


def load_agent_config() -> AgentConfig:
    settings = get_settings()
    return AgentConfig(model_spec=settings.model, instructions=settings.agent_instructions)
