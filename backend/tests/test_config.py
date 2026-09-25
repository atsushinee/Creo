"""Tests for .env loading into the process environment."""

import os
from pathlib import Path

from app.core.config import load_env_file


def test_load_env_file_sets_provider_native_key(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=sk-env-test\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    load_env_file(env_file)

    assert os.environ["OPENAI_API_KEY"] == "sk-env-test"


def test_load_env_file_never_overrides_real_env(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=sk-from-file\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-shell")

    load_env_file(env_file)

    assert os.environ["OPENAI_API_KEY"] == "sk-from-shell"


def test_backend_env_file_is_loaded_on_import() -> None:
    """The real backend/.env (if present) reaches os.environ — the bug this
    guards against: provider-native keys written in .env were invisible."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return  # nothing to verify on machines without a local .env
    expected_name = "OPENAI_API_KEY"
    loaded = any(name == expected_name for name in os.environ)
    if f"{expected_name}=" in env_path.read_text(encoding="utf-8"):
        assert loaded, f"{expected_name} from backend/.env must be in os.environ"
