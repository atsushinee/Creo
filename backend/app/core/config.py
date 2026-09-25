"""Application settings (pydantic-settings, CREO_ env prefix)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CREO_", env_file=".env", extra="ignore")

    model: str = "openai:gpt-4o-mini"
    agent_instructions: str = (
        "You are Creo, a precise and helpful AI agent working inside the Creo workspace. "
        "Use the provided tools when they help, and keep answers clear and concise."
    )
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
