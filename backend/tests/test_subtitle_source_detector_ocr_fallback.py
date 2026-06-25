from __future__ import annotations

from pathlib import Path

from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, DouyinVideoItem
from app.modules.douyin_reup.subtitle_source_detector import SubtitleSourceDetector
from app.modules.hardsub_ocr.hardsub_ocr_schema import HardSubOCRResult, OCRSubtitleLine


LINE_1 = "\u8fd9\u4e2a\u676f\u5b50\u62ff\u8d77\u6765\u5f88\u7a33"
LINE_2 = "\u624b\u67c4\u63e1\u8d77\u6765\u4e5f\u8212\u670d"
LINE_3 = "\u653e\u684c\u4e0a\u770b\u7740\u5f88\u5e72\u51c0"


class FailingASR:
    warnings: list[str] = []

    def transcribe_to_srt(self, *args, **kwargs):
        raise RuntimeError("ASR failed")


class SuccessfulASR:
    warnings: list[str] = []

    def __init__(self) -> None:
        self.called = False

    def transcribe_to_srt(self, _video_path, output_path, **_kwargs):
        self.called = True
        path = Path(output_path)
        path.write_text(
            f"1\n00:00:00,000 --> 00:00:01,200\n{LINE_1}\n\n"
            f"2\n00:00:01,500 --> 00:00:02,800\n{LINE_2}\n\n"
            f"3\n00:00:03,000 --> 00:00:04,200\n{LINE_3}\n",
            encoding="utf-8",
        )
        return str(path)


class FakeOCR:
    def extract_hardsub_to_srt(self, video_path, output_dir, settings):
        srt = Path(output_dir) / "video_source_zh_ocr.srt"
        srt.write_text(
            f"1\n00:00:00,000 --> 00:00:01,200\n{LINE_1}\n\n"
            f"2\n00:00:01,500 --> 00:00:02,800\n{LINE_2}\n",
            encoding="utf-8",
        )
        return HardSubOCRResult(
            video_path=video_path,
            provider="mock_ocr",
            language="ch",
            region_mode="bottom_auto",
            source_srt_path=str(srt),
            debug_json_path=str(Path(output_dir) / "ocr_debug.json"),
            frame_count=3,
            detected_line_count=2,
            average_confidence=0.9,
            lines=[
                OCRSubtitleLine(index=1, start_ms=0, end_ms=1200, text=LINE_1, confidence=0.9, frame_count=3),
                OCRSubtitleLine(index=2, start_ms=1500, end_ms=2800, text=LINE_2, confidence=0.9, frame_count=3),
            ],
        )


def _video(tmp_path: Path) -> DouyinVideoItem:
    return DouyinVideoItem(
        path=str(tmp_path / "clip.mp4"),
        filename="clip.mp4",
        duration=8,
        width=1080,
        height=1920,
        fps=30,
        has_audio=True,
        embedded_subtitle_found=False,
    )


def test_asr_fail_falls_back_to_ocr(tmp_path: Path):
    settings = DouyinReupSettings(
        enabled=True,
        subtitle_source_priority=["asr", "ocr_hardsub"],
        use_ocr_if_asr_failed=True,
        ocr_provider="mock_ocr",
        asr_subprocess_isolation=False,
        ocr_subprocess_isolation=False,
    )

    result = SubtitleSourceDetector(asr_service=FailingASR(), ocr_service=FakeOCR()).detect_source(
        _video(tmp_path),
        settings,
        str(tmp_path / "work"),
    )

    assert result.source_type == "ocr_hardsub"
    assert result.source_srt_path
    assert result.ocr_detected_line_count == 2
    assert result.subtitle_rejected_sources == []


def test_full_frame_ocr_is_tried_before_asr(tmp_path: Path):
    asr = SuccessfulASR()
    settings = DouyinReupSettings(
        enabled=True,
        ocr_region_mode="full_frame",
        prefer_ocr_over_asr_when_text_visible=False,
        ocr_provider="mock_ocr",
        asr_subprocess_isolation=False,
        ocr_subprocess_isolation=False,
    )

    result = SubtitleSourceDetector(asr_service=asr, ocr_service=FakeOCR()).detect_source(
        _video(tmp_path),
        settings,
        str(tmp_path / "work"),
    )

    assert result.source_type == "ocr_hardsub"
    assert result.ocr_detected_line_count == 2
    assert asr.called is False
