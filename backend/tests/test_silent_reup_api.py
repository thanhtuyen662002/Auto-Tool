from __future__ import annotations

from fastapi.testclient import TestClient

from app import database
from app.api import create_app
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
