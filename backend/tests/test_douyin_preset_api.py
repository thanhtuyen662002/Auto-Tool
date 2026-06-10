from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import create_app
from app.modules.douyin_reup.douyin_schema import DouyinVideoItem


def test_douyin_preset_list_detail_and_apply_api(monkeypatch):
    monkeypatch.setattr("app.api.start_background_dependency_warmup", lambda **_kwargs: None)

    with TestClient(create_app()) as client:
        presets = client.get("/api/douyin-reup/presets")
        assert presets.status_code == 200
        preset_ids = {preset["id"] for preset in presets.json()["presets"]}
        assert len(preset_ids) == 9
        assert "silent_chill_immersive" in preset_ids

        detail = client.get("/api/douyin-reup/presets/ocr_priority")
        assert detail.status_code == 200
        assert detail.json()["id"] == "ocr_priority"

        applied = client.post(
            "/api/douyin-reup/apply-preset",
            json={"preset_id": "fast_auto", "overrides": {"max_videos": 2}},
        )
        assert applied.status_code == 200
        payload = applied.json()
        assert payload["settings"]["preset_id"] == "fast_auto"
        assert payload["settings"]["auto_render_after_translation"] is True
        assert payload["settings"]["max_videos"] == 2


def test_douyin_recommend_preset_api_uses_scan_signals(tmp_path, monkeypatch):
    monkeypatch.setattr("app.api.start_background_dependency_warmup", lambda **_kwargs: None)
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    class FakeScanner:
        def scan_folder(self, _folder):
            return [
                DouyinVideoItem(path="a.mp4", filename="a.mp4", duration=8, width=1080, height=1920, fps=30, has_audio=False),
                DouyinVideoItem(path="b.mp4", filename="b.mp4", duration=8, width=1080, height=1920, fps=30, has_audio=False),
                DouyinVideoItem(path="c.mp4", filename="c.mp4", duration=8, width=1080, height=1920, fps=30, has_audio=True),
            ]

    monkeypatch.setattr("app.api.DouyinFolderScanner", FakeScanner)

    with TestClient(create_app()) as client:
        response = client.post("/api/douyin-reup/recommend-preset", json={"source_folder": str(source_dir)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["preset_id"] == "silent_chill_immersive"
    assert payload["signals"]["total"] == 3
