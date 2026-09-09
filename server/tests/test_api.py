"""HTTP 端到端冒烟测试（不依赖真实模型）。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def setup_config(monkeypatch):
    test_yaml = Path(__file__).parent / "fixtures" / "trae.test.yaml"
    monkeypatch.setenv("TRAE_CONFIG", str(test_yaml))


def test_health_endpoint():
    from trae_server.main import create_app

    app = create_app()
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


def test_root_endpoint():
    from trae_server.main import create_app

    app = create_app()
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["name"] == "trae-ide-clone"


def test_models_endpoint_requires_auth():
    from trae_server.main import create_app

    app = create_app()
    with TestClient(app) as client:
        r = client.get("/v1/models")
        assert r.status_code == 401


def test_models_endpoint_with_auth():
    from trae_server.main import create_app

    app = create_app()
    with TestClient(app) as client:
        r = client.get("/v1/models", headers={"X-API-Key": "test-key"})
        assert r.status_code == 200
        data = r.json()
        assert "providers" in data