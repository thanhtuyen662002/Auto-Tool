from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.api import create_app


def test_content_api_flow_builds_updates_marks_and_exports(tmp_path):
    client, project_id, output_dir = _client_with_project_and_output(tmp_path)

    response = client.get(f"/api/projects/{project_id}/content")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total_items"] == 1
    assert payload["items"][0]["caption"] == "Caption API"

    update = client.put(
        f"/api/projects/{project_id}/content/1",
        json={
            "caption": "Caption đã chỉnh từ UI",
            "hashtags": "#ui #autotool",
            "cta": "Đặt hàng ngay",
            "user_note": "Đăng Shopee",
        },
    )
    assert update.status_code == 200
    assert update.json()["item"]["hashtags"] == ["#ui", "#autotool"]

    copied = client.post(f"/api/projects/{project_id}/content/1/mark-copied")
    assert copied.status_code == 200
    assert copied.json()["item"]["publish_status"] == "copied"

    posted = client.post(
        f"/api/projects/{project_id}/content/1/mark-posted",
        json={"platform": "TikTok"},
    )
    assert posted.status_code == 200
    assert posted.json()["item"]["publish_status"] == "posted"
    assert posted.json()["item"]["platform"] == "TikTok"

    exported = client.post(
        f"/api/projects/{project_id}/content/export",
        json={"formats": ["json", "csv", "txt", "md"]},
    )
    assert exported.status_code == 200
    assert (output_dir / "content_export.json").exists()
    assert len(exported.json()["files"]) == 5


def _client_with_project_and_output(tmp_path: Path) -> tuple[TestClient, str, Path]:
    database.DB_PATH = tmp_path / "content-api.db"
    app = create_app()
    client = TestClient(app)
    database.init_db()

    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir()
    output_dir.mkdir()
    response = client.post("/api/projects", json=_config(source_dir, output_dir))
    assert response.status_code == 200
    project_id = response.json()["project_id"]

    script_path = output_dir / "video_001_script.json"
    script_path.write_text(
        json.dumps(
            {
                "hook": "Hook API",
                "voiceover": [{"time_hint": "0-3s", "text": "Voice"}],
                "subtitles": [{"start_hint": 0, "end_hint": 3, "text": "Voice"}],
                "cta": "Xem chi tiết",
                "caption": "Caption API",
                "hashtags": ["#api"],
                "variant_style_id": "reviewer_natural",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    timeline_path = output_dir / "video_001_timeline.json"
    timeline_path.write_text(json.dumps({"template_id": "ugc_reviewer_natural"}), encoding="utf-8")
    video_path = output_dir / "video_001.mp4"
    video_path.write_bytes(b"video")

    database.create_job("job-content-api", project_id, preview_only=False, total_outputs=1)
    database.update_job(
        "job-content-api",
        status="completed",
        output_folder=str(output_dir),
        results_json=json.dumps(
            {
                "outputs": [
                    {
                        "index": 1,
                        "path": str(video_path),
                        "status": "success",
                        "script_file": str(script_path),
                        "timeline_file": str(timeline_path),
                    }
                ]
            },
            ensure_ascii=False,
        ),
    )
    return client, project_id, output_dir


def _config(source_dir: Path, output_dir: Path) -> dict:
    return {
        "project_name": "content-api-test",
        "source_folder": str(source_dir),
        "output_folder": str(output_dir),
        "product": {
            "name": "Sản phẩm test",
            "brand": "Brand",
            "description": "Mô tả sản phẩm",
            "features": ["Tính năng"],
            "cta": "Xem chi tiết",
        },
        "render": {
            "output_count": 1,
            "duration": 12,
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
    }
