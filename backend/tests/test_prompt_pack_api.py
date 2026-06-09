from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api import create_app
from backend.tests.prompt_pack_helpers import add_main_asset, make_project


def test_prompt_pack_api_returns_prompt_pack_and_file_paths(tmp_path: Path) -> None:
    project_id = make_project(tmp_path)
    add_main_asset(project_id, tmp_path)
    client = TestClient(create_app())

    response = client.post(
        f"/api/projects/{project_id}/video-prompt-pack",
        json={"duration_seconds": 8, "scene_count": 5, "model_hint": "omni"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["prompt_pack"]["product_name"] == "Máy Chiếu 4K Android KAW XMAX10"
    assert payload["files"]["video_prompt_full"].endswith("video_prompt_full.txt")
    assert Path(payload["files"]["video_prompt_pack_json"]).exists()


def test_reference_summary_api_returns_missing_asset_warning(tmp_path: Path) -> None:
    project_id = make_project(tmp_path)
    client = TestClient(create_app())

    response = client.post(f"/api/projects/{project_id}/reference-summary")

    assert response.status_code == 200
    warnings = response.json()["summary"]["warnings"]
    assert any("Chưa có ảnh tham chiếu" in warning for warning in warnings)
