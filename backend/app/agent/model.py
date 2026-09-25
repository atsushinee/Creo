"""LLM model construction (init_chat_model spec: '<provider>:<model>')."""

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel


def create_model(model_spec: str) -> BaseChatModel:
    """Build a LangChain chat model from an init_chat_model spec.

    Provider API keys are read from provider-native env vars by the
    integration packages themselves (e.g. OPENAI_API_KEY, ANTHROPIC_API_KEY).
    """
    return init_chat_model(model_spec)
