from pathlib import Path

from fastapi.testclient import TestClient

from app.api import create_app


def test_single_port_serves_spa_assets_and_protects_api(monkeypatch, tmp_path: Path) -> None:
    dist = tmp_path / "frontend" / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text('<html><div id="root">single-port</div></html>', encoding="utf-8")
    (assets / "app.js").write_text("window.AUTO_TOOL_TEST = true;", encoding="utf-8")
    monkeypatch.setenv("AUTO_TOOL_ROOT", str(tmp_path))
    monkeypatch.setenv("AUTO_TOOL_STARTUP_DEPENDENCY_WARMUP", "0")

    with TestClient(create_app()) as client:
        health = client.get("/api/health")
        dashboard = client.get("/dashboard")
        asset = client.get("/assets/app.js")
        missing_api = client.get("/api/not-found")
        docs = client.get("/docs")
        status = client.get("/api/local-app/frontend-status")

    assert health.status_code == 200
    assert health.headers["content-type"].startswith("application/json")
    assert dashboard.status_code == 200
    assert "single-port" in dashboard.text
    assert asset.status_code == 200
    assert "AUTO_TOOL_TEST" in asset.text
    assert missing_api.status_code == 404
    assert missing_api.headers["content-type"].startswith("application/json")
    assert missing_api.json() == {"detail": "Not Found"}
    assert docs.status_code == 200
    assert status.status_code == 200
    assert status.json()["data"]["served_by_backend"] is True
