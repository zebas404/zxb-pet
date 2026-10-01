from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app

VAULT = Path(__file__).parent / "fixtures" / "vault"
TODAY = date(2026, 10, 6)  # Fase 1 of the demo roadmap; Fase 0 already ended


@pytest.fixture
def vault() -> Path:
    return VAULT


@pytest.fixture
def settings(tmp_path, monkeypatch) -> Settings:
    s = Settings(_env_file=None, vault_path=VAULT, data_dir=tmp_path, anthropic_api_key=None)
    monkeypatch.setattr(Settings, "today", lambda self: TODAY)
    return s


@pytest.fixture
def client(settings):
    app.dependency_overrides[get_settings] = lambda: settings
    yield TestClient(app)
    app.dependency_overrides.clear()
