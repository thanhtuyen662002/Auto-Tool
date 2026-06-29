from __future__ import annotations

from pathlib import Path

from app.modules.douyin_reup.douyin_reup_service import DouyinReupService
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, DouyinVideoItem
from app.modules.hardsub_ocr.hardsub_ocr_schema import HardSubOCRResult, OCRSubtitleLine


class FallbackProbeDetector:
    def __init__(self) -> None:
        self.attempts: list[str] = []
        self.last_probe_ocr_error: str | None = None

    def probe_ocr_debug(self, video, settings, target_dir, progress_callback=None):
        self.attempts.append(settings.ocr_provider)
        if settings.ocr_provider == "paddleocr":
            self.last_probe_ocr_error = "Khong tim thay Python runtime phu hop de cai PaddleOCR."
            return None

        self.last_probe_ocr_error = None
        debug_path = Path(target_dir) / "ocr_debug.json"
        debug_path.write_text("{}", encoding="utf-8")
        return HardSubOCRResult(
            video_path=video.path,
            provider="easyocr",
            language="ch",
            region_mode=settings.ocr_region_mode,
            source_srt_path=None,
            debug_json_path=str(debug_path),
            frame_count=1,
            detected_line_count=1,
            average_confidence=0.91,
            lines=[
                OCRSubtitleLine(
                    index=1,
                    start_ms=0,
                    end_ms=1000,
                    text="\u5b57\u5e55",
                    confidence=0.91,
                    frame_count=1,
                )
            ],
        )


def test_cover_probe_falls_back_to_easyocr_when_paddle_unavailable(tmp_path: Path):
    detector = FallbackProbeDetector()
    service = DouyinReupService(source_detector=detector)
    settings = DouyinReupSettings(
        enabled=True,
        burn_subtitle=True,
        subtitle_cover_enabled=True,
        subtitle_cover_auto_position=True,
        subtitle_cover_probe_if_no_ocr=True,
        ocr_provider="paddleocr",
        ocr_sample_fps=1.5,
        subtitle_cover_probe_sample_fps=1.5,
    )
    video = DouyinVideoItem(
        path=str(tmp_path / "clip.mp4"),
        filename="clip.mp4",
        duration=5,
        width=720,
        height=1280,
        fps=30,
        has_audio=True,
    )
    warnings: list[str] = []

    debug_path = service._probe_cover_ocr_debug(video=video, settings=settings, video_dir=tmp_path, warnings=warnings)

    assert debug_path
    assert detector.attempts == ["paddleocr", "easyocr"]
    assert any("subtitle_cover_probe_fallback" in warning for warning in warnings)
    assert any("subtitle_cover_probe" in warning for warning in warnings)
