from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import create_app


def test_health_reports_v02_rc_version() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["version"] == "0.2.0-rc1"
