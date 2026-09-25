"""LLM model construction (init_chat_model based, provider-agnostic).

Any provider supported by `init_chat_model` works. For OpenAI-compatible
endpoints (DeepSeek, Qwen, Moonshot, Ollama, vLLM, ...), set
CREO_MODEL_BASE_URL + CREO_MODEL_API_KEY + CREO_MODEL_PROVIDER=openai.
"""

from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel


def create_model(
    provider: str,
    name: str,
    api_key: str | None = None,
    base_url: str | None = None,
) -> BaseChatModel:
    """Build a chat model from provider + model name.

    `api_key` / `base_url` are optional overrides: when empty, the provider
    integration reads its own native env vars (e.g. OPENAI_API_KEY) and uses
    its default endpoint. Only non-empty values are forwarded so providers
    without those fields (e.g. google_genai) stay usable.
    """
    kwargs: dict[str, Any] = {}
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url
    return init_chat_model(name, model_provider=provider, **kwargs)
