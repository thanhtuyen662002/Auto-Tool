from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.api import create_app


def test_visual_style_api_lists_previews_and_updates_project(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AUTO_TOOL_DATA_DIR", str(tmp_path / "data"))
    database.DB_PATH = tmp_path / "autotool-style-test.db"

    with TestClient(create_app()) as client:
        presets_response = client.get("/api/visual-styles")
        assert presets_response.status_code == 200
        presets = presets_response.json()["presets"]
        assert len(presets) >= 8
        assert any(item["id"] == "clean_review_light" for item in presets)

        preview_response = client.post(
            "/api/visual-styles/preview",
            json={
                "preset_id": "tech_dark_neon",
                "sample_text": "Một câu subtitle preview",
                "resolution": "360x640",
            },
        )
        assert preview_response.status_code == 200
        preview_payload = preview_response.json()
        preview_path = Path(preview_payload["preview_image_path"])
        assert preview_payload["success"] is True
        assert preview_payload["preview_image_url"].startswith("/api/files/image")
        assert preview_path.exists()

        image_response = client.get("/api/files/image", params={"path": str(preview_path)})
        assert image_response.status_code == 200
        assert image_response.headers["content-type"].startswith("image/png")

        project_response = client.post("/api/projects", json=_project_config(tmp_path))
        assert project_response.status_code == 200
        project_id = project_response.json()["project_id"]

        update_response = client.put(
            f"/api/projects/{project_id}/visual-style",
            json={"preset_id": "sale_bold_red"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["visual_style"]["preset_id"] == "sale_bold_red"

        project_detail = client.get(f"/api/projects/{project_id}")
        assert project_detail.status_code == 200
        assert project_detail.json()["config"]["visual_style"]["preset_id"] == "sale_bold_red"


def test_image_file_api_allows_user_selected_background(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AUTO_TOOL_DATA_DIR", str(tmp_path / "data"))
    database.DB_PATH = tmp_path / "autotool-style-test.db"
    background = tmp_path / "outside-app-data" / "background.webp"
    background.parent.mkdir()
    background.write_bytes(b"not-a-real-image-but-preview-endpoint-serves-by-extension")

    with TestClient(create_app()) as client:
        response = client.get("/api/files/image", params={"path": str(background)})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/webp")


def test_remote_image_api_proxies_external_background(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AUTO_TOOL_DATA_DIR", str(tmp_path / "data"))
    database.DB_PATH = tmp_path / "autotool-style-test.db"

    class FakeRemoteImageResponse:
        status_code = 200
        headers = {"content-type": "image/png"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def iter_content(self, chunk_size: int):
            yield b"\x89PNG\r\n"

    def fake_get(url: str, **_kwargs):
        assert url == "https://example.com/background.png"
        return FakeRemoteImageResponse()

    import requests

    monkeypatch.setattr(requests, "get", fake_get)
    with TestClient(create_app()) as client:
        response = client.get("/api/files/remote-image", params={"url": "https://example.com/background.png"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content.startswith(b"\x89PNG")


def _project_config(tmp_path: Path) -> dict:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)
    return {
        "project_name": "visual-style-api-test",
        "source_folder": str(source_dir),
        "output_folder": str(output_dir),
        "product": {
            "name": "Máy chiếu test",
            "brand": "KAW",
            "description": "Mô tả test.",
            "features": ["Hỗ trợ 4K"],
            "cta": "Xem ngay",
        },
        "render": {
            "output_count": 1,
            "duration": 8,
            "aspect_ratio": "9:16",
            "resolution": "1080x1920",
            "fps": 30,
        },
        "effects": {
            "cut_intensity": 70,
            "speed_variation": 30,
            "grain": 0,
            "zoom_motion": 0,
            "overlay_height": 33,
            "subtitle_size": 84,
        },
        "ai": {
            "text_model": "gemini-test",
            "tone": "friendly_reviewer",
            "language": "vi",
            "gemini_api_keys": [],
        },
        "music": {
            "enabled": False,
            "source_folder": None,
            "source_file": None,
            "volume": 0.12,
            "fade_in": 0.5,
            "fade_out": 0.8,
            "duck_under_voice": False,
        },
        "visual_style": {
            "preset_id": "clean_review_light",
            "custom_overrides": None,
        },
    }
