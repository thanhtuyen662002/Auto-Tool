from __future__ import annotations

from fastapi.testclient import TestClient

import app.api as api_module
from app.api import create_app


def test_health_reports_douyin_reup_v1_rc_version() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["version"] == "1.0.0-rc1"
    assert response.json()["capabilities"] == {
        "douyin_reup": True,
        "silent_immersive_mode": True,
    }


def test_browse_path_endpoint_returns_selected_path(monkeypatch) -> None:
    client = TestClient(create_app())

    def fake_browse_local_path(mode, title=None, initial_path=None, extensions=None):
        assert mode == "folder"
        assert title == "Chọn thư mục video nguồn"
        assert initial_path == "examples/sample_videos"
        assert extensions == []
        return "D:\\Videos\\Input"

    monkeypatch.setattr(api_module, "browse_local_path", fake_browse_local_path)

    response = client.post(
        "/api/system/browse-path",
        json={
            "mode": "folder",
            "title": "Chọn thư mục video nguồn",
            "initial_path": "examples/sample_videos",
            "extensions": [],
        },
    )

    assert response.status_code == 200
    assert response.json() == {"path": "D:\\Videos\\Input", "cancelled": False}
