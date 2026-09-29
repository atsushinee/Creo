"""Shared test isolation.

backend/.env is loaded into the process environment at config import time.
With CREO_KB_ENABLED=true and real endpoints configured, every create_app()
lifespan would construct real Milvus/Unstructured clients and dial external
services during tests. The autouse fixture below swaps in a hermetic settings
profile (KB disabled, no ambient CREO_* vars); tests that need the KB stack
stub app.state explicitly (test_kb_api.py), so no test should rely on ambient
configuration.
"""

import os

import pytest

from app.core.config import Settings

_HERMETIC_SETTINGS = Settings(_env_file=None, kb_enabled=False)


@pytest.fixture(autouse=True)
def hermetic_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    for name in list(os.environ):
        if name.startswith("CREO_"):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("app.main.get_settings", lambda: _HERMETIC_SETTINGS)
    monkeypatch.setattr("app.api.routes.knowledge.get_settings", lambda: _HERMETIC_SETTINGS)
    return _HERMETIC_SETTINGS
