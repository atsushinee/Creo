"""Shared test isolation.

backend/.env is loaded into the process environment at config import time.
With CREO_KB_ENABLED=true and real endpoints configured, every create_app()
lifespan would construct real Milvus/Unstructured clients and dial external
services during tests. The autouse fixture below swaps in a hermetic settings
profile: KB disabled, no ambient CREO_* vars, and all on-disk state (sessions,
checkpoints, KB registry) redirected to a per-test tmp dir — tests must never
read or write the real data/ directory. Tests that need the KB stack stub
app.state explicitly (test_kb_api.py).
"""

import os

import pytest

from app.core.config import Settings


@pytest.fixture(autouse=True)
def hermetic_settings(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Settings:
    for name in list(os.environ):
        if name.startswith("CREO_"):
            monkeypatch.delenv(name, raising=False)
    settings = Settings(
        _env_file=None,
        kb_enabled=False,
        data_dir=tmp_path / "data",
        kb_data_dir=tmp_path / "data" / "kb",
    )
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.routes.knowledge.get_settings", lambda: settings)
    return settings
