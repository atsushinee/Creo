"""Application settings (pydantic-settings, CREO_ env prefix)."""

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def load_env_file(path: Path | None = None) -> None:
    """Load backend/.env into the process environment.

    Provider SDKs (openai / anthropic / ...) read their native keys (e.g.
    OPENAI_API_KEY) from os.environ, while pydantic-settings only maps
    CREO_-prefixed variables into Settings — without this step, keys written
    in .env never reach them. Existing process env vars win (override=False).
    """
    load_dotenv(path or BACKEND_ROOT / ".env", override=False)


# Must run before Settings is first constructed (get_settings is cached).
load_env_file()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CREO_", env_file=".env", extra="ignore")

    # --- LLM (any init_chat_model provider; OpenAI-compatible endpoints
    #     such as DeepSeek/Qwen/Ollama/vLLM work via CREO_MODEL_BASE_URL) ---
    model_provider: str = "openai"
    model_name: str = "gpt-4o-mini"
    # Optional overrides; when empty, the provider integration falls back to
    # its native env vars (e.g. OPENAI_API_KEY) and default endpoint.
    model_api_key: str = ""
    model_base_url: str = ""

    agent_instructions: str = (
        "You are Creo, a precise and helpful AI agent working inside the Creo workspace. "
        "Use the provided tools when they help, and keep answers clear and concise."
    )
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    log_level: str = "INFO"

    # --- Knowledge base (ADR-0004; disabled unless enabled AND fully
    #     configured — the lifespan skips the stack when endpoints are empty) ---
    kb_enabled: bool = False
    kb_data_dir: Path = BACKEND_ROOT / "data" / "kb"
    milvus_uri: str = ""  # Zilliz Cloud endpoint or http://host:19530
    milvus_token: str = ""  # Zilliz Cloud API key (empty for unauthenticated self-hosting)
    unstructured_api_url: str = ""  # e.g. http://localhost:8000
    unstructured_api_key: str = ""
    unstructured_timeout: float = 600.0  # hi_res on large PDFs is slow
    unstructured_strategy: str = "hi_res"  # auto | fast | hi_res | ocr_only
    unstructured_languages: str = "chi_sim,eng"  # OCR languages, comma-separated
    kb_embedding_base_url: str = ""  # OpenAI-compatible, e.g. https://api.siliconflow.cn/v1
    kb_embedding_api_key: str = ""
    kb_embedding_model: str = "BAAI/bge-m3"
    kb_embedding_dim: int = 1024
    # Analyzer is fixed at collection creation; 'chinese' is jieba-based.
    # Changing model/dim/analyzer requires re-creating the collections.
    kb_analyzer: str = "chinese"
    kb_chunk_max_characters: int = 1500
    kb_upload_max_mb: int = 50
    kb_search_top_k: int = 5

    @property
    def model_display(self) -> str:
        return f"{self.model_provider}:{self.model_name}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def unstructured_language_list(self) -> list[str]:
        return [lang.strip() for lang in self.unstructured_languages.split(",") if lang.strip()]

    @property
    def kb_upload_max_bytes(self) -> int:
        return self.kb_upload_max_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
