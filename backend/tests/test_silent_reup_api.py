from __future__ import annotations

from fastapi.testclient import TestClient

from app import database
from app.api import create_app
from app.modules.douyin_reup.douyin_schema import DouyinVideoItem
from app.modules.silent_immersive_reup.silent_schema import SilentReupPlan, SilentVisualSegment


def test_silent_detect_and_plan_api(tmp_path, monkeypatch):
    database.DB_PATH = tmp_path / "autotool-silent-test.db"
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")

    class FakeService:
        def detect_folder(self, source_folder):
            return [
                {
                    "video_path": str(video),
                    "has_speech": False,
                    "speech_score": 0.1,
                    "recommended_mode": "silent_immersive",
                    "method": "fake",
                    "warnings": [],
                }
            ]

        def build_plan(self, video_path, settings=None, output_dir=None, product_context=None):
            return SilentReupPlan(
                video_path=video_path,
                strategy="chill_immersive",
                has_speech=False,
                speech_score=0.1,
                visual_segments=[
                    SilentVisualSegment(id="seg_001", video_path=video_path, start=0, end=2, duration=2)
                ],
                captions=[
                    {
                        "index": 1,
                        "start": 0,
                        "end": 2,
                        "text": "Caption thử nghiệm",
                        "source": "visual_generated",
                    }
                ],
                recommended_audio_mode="original_audio_plus_bgm",
            )

    monkeypatch.setattr("app.api.SilentReupService", FakeService)
    monkeypatch.setattr("app.api.start_background_dependency_warmup", lambda **_kwargs: None)

    class FakeThread:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def start(self):
            return None

    monkeypatch.setattr("app.api.threading.Thread", FakeThread)

    with TestClient(create_app()) as client:
        detected = client.post("/api/silent-reup/detect", json={"source_folder": str(tmp_path)})
        assert detected.status_code == 200
        assert detected.json()["items"][0]["recommended_mode"] == "silent_immersive"

        planned = client.post(
            "/api/silent-reup/plan",
            json={"video_path": str(video), "settings": {"use_ocr_if_no_subtitle": False}, "product_context": {}},
        )
        assert planned.status_code == 200
        payload = planned.json()
        assert payload["success"] is True
        assert payload["plan_id"]

        rendered = client.post(
            "/api/silent-reup/render",
            json={"plan_id": payload["plan_id"], "settings": {"use_ocr_if_no_subtitle": False}},
        )
        assert rendered.status_code == 200
        assert rendered.json()["job_id"]


def test_silent_one_click_api_queues_batch(tmp_path, monkeypatch):
    database.DB_PATH = tmp_path / "silent-one-click.db"
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    video = source / "clip.mp4"
    video.write_bytes(b"fake")

    class FakeScanner:
        def scan_folder(self, _source_folder):
            return [
                DouyinVideoItem(
                    path=str(video),
                    filename=video.name,
                    duration=5,
                    width=1080,
                    height=1920,
                    fps=30,
                    has_audio=True,
                )
            ]

    class FakeThread:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            return None

    monkeypatch.setattr("app.api.DouyinFolderScanner", FakeScanner)
    monkeypatch.setattr("app.api.threading.Thread", FakeThread)
    monkeypatch.setattr("app.api.start_background_dependency_warmup", lambda **_kwargs: None)

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/silent-reup/one-click",
            json={
                "project_name": "silent-batch",
                "source_folder": str(source),
                "output_folder": str(output),
                "strategy": "chill_immersive",
                "review_before_render": True,
                "product_context": {"product_name": "Ke bep"},
            },
        )

    assert response.status_code == 200
    assert response.json()["preset_id"] == "silent_chill_immersive"
    assert response.json()["total_outputs"] == 1
