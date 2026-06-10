from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api import create_app
from app.modules.hardsub_ocr.hardsub_ocr_schema import HardSubOCRResult, OCRSubtitleLine


def test_douyin_ocr_test_api_returns_result(tmp_path: Path, monkeypatch):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")

    class FakeService:
        def extract_hardsub_to_srt(self, video_path, output_dir, settings):
            return HardSubOCRResult(
                video_path=video_path,
                provider="mock_ocr",
                language="ch",
                region_mode="bottom_auto",
                source_srt_path=str(Path(output_dir) / "source.srt"),
                debug_json_path=str(Path(output_dir) / "debug.json"),
                frame_count=2,
                detected_line_count=1,
                average_confidence=0.8,
                lines=[OCRSubtitleLine(index=1, start_ms=0, end_ms=1000, text="这个真的很好用", confidence=0.8, frame_count=2)],
            )

    monkeypatch.setattr("app.api.HardSubOCRService", FakeService)

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/douyin-reup/ocr-test",
            json={"video_path": str(video), "settings": {"ocr_provider": "mock_ocr"}},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["result"]["detected_line_count"] == 1
