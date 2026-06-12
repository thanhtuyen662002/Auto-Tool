from fastapi.testclient import TestClient

from app.api import create_app


def test_silent_v1_health_and_frontend_endpoints_are_available(monkeypatch):
    monkeypatch.setattr("app.api.start_background_dependency_warmup", lambda **_kwargs: None)
    app = create_app()
    paths = app.openapi()["paths"]

    with TestClient(app) as client:
        health = client.get("/api/health")
        presets = client.get("/api/douyin-reup/presets")
        industries = client.get("/api/silent-caption-templates/industries")

    assert health.json()["capabilities"]["silent_immersive_mode"] is True
    assert presets.status_code == 200
    assert industries.status_code == 200
    for path in [
        "/api/silent-reup/detect",
        "/api/silent-reup/one-click",
        "/api/silent-reup/plan",
        "/api/silent-reup/render",
        "/api/silent-reup/plans/{plan_id}/visual-tags",
        "/api/silent-reup/plans/{plan_id}/segments/{segment_id}/tags",
        "/api/silent-reup/plans/{plan_id}/regenerate-captions",
        "/api/subtitle-review/documents/{document_id}",
        "/api/subtitle-review/documents/{document_id}/approve",
        "/api/subtitle-review/documents/{document_id}/render",
        "/api/final-output-qa/jobs/{job_id}/check",
        "/api/douyin-reup/jobs/{job_id}/export-pack",
    ]:
        assert path in paths

