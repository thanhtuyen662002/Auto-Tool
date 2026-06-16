from __future__ import annotations

from pathlib import Path

from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, DouyinVideoItem
from app.modules.douyin_reup.subtitle_source_detector import SubtitleSourceDetector
from app.modules.hardsub_ocr.hardsub_ocr_schema import HardSubOCRResult, OCRSubtitleLine


class FailingASR:
    warnings: list[str] = []

    def transcribe_to_srt(self, *args, **kwargs):
        raise RuntimeError("ASR failed")


class FakeOCR:
    def extract_hardsub_to_srt(self, video_path, output_dir, settings):
        srt = Path(output_dir) / "video_source_zh_ocr.srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\n这个真的很好用\n", encoding="utf-8")
        return HardSubOCRResult(
            video_path=video_path,
            provider="mock_ocr",
            language="ch",
            region_mode="bottom_auto",
            source_srt_path=str(srt),
            debug_json_path=str(Path(output_dir) / "ocr_debug.json"),
            frame_count=3,
            detected_line_count=1,
            average_confidence=0.9,
            lines=[OCRSubtitleLine(index=1, start_ms=0, end_ms=1000, text="这个真的很好用", confidence=0.9, frame_count=3)],
        )


def test_asr_fail_falls_back_to_ocr(tmp_path: Path):
    video = DouyinVideoItem(
        path=str(tmp_path / "clip.mp4"),
        filename="clip.mp4",
        duration=8,
        width=1080,
        height=1920,
        fps=30,
        has_audio=True,
        embedded_subtitle_found=False,
    )
    settings = DouyinReupSettings(
        enabled=True,
        use_ocr_if_asr_failed=True,
        ocr_provider="mock_ocr",
        asr_subprocess_isolation=False,
        ocr_subprocess_isolation=False,
    )

    result = SubtitleSourceDetector(asr_service=FailingASR(), ocr_service=FakeOCR()).detect_source(video, settings, str(tmp_path / "work"))

    assert result.source_type == "ocr_hardsub"
    assert result.source_srt_path
    assert result.ocr_detected_line_count == 1
