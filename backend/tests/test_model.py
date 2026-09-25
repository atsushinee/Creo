"""Tests for provider-agnostic model construction and settings parsing."""

import os

from app.agent.model import create_model
from app.core.config import Settings


def _clear_creo_env(monkeypatch) -> None:
    """Remove ambient CREO_* variables so tests are immune to the real .env."""
    for name in list(os.environ):
        if name.startswith("CREO_"):
            monkeypatch.delenv(name, raising=False)


def test_create_model_openai_compatible_custom_endpoint() -> None:
    model = create_model(
        provider="openai",
        name="deepseek-chat",
        api_key="test-key",
        base_url="https://api.deepseek.com/v1",
    )
    # ChatOpenAI stores the overrides under these attributes.
    assert model.openai_api_base == "https://api.deepseek.com/v1"
    assert model.openai_api_key.get_secret_value() == "test-key"


def test_create_model_official_openai_defaults() -> None:
    model = create_model(provider="openai", name="gpt-4o-mini", api_key="test-key")
    assert model.openai_api_base is None or "api.openai.com" in str(model.openai_api_base)


def test_settings_parse_custom_llm_env(monkeypatch) -> None:
    _clear_creo_env(monkeypatch)
    monkeypatch.setenv("CREO_MODEL_PROVIDER", "openai")
    monkeypatch.setenv("CREO_MODEL_NAME", "deepseek-reasoner")
    monkeypatch.setenv("CREO_MODEL_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("CREO_MODEL_API_KEY", "sk-test")

    settings = Settings(_env_file=None)
    assert settings.model_display == "openai:deepseek-reasoner"
    assert settings.model_base_url == "https://api.deepseek.com/v1"
    assert settings.model_api_key == "sk-test"


def test_settings_defaults(monkeypatch) -> None:
    _clear_creo_env(monkeypatch)
    settings = Settings(_env_file=None)
    assert settings.model_display == "openai:gpt-4o-mini"
    assert settings.model_base_url == ""
