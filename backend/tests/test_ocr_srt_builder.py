from __future__ import annotations

from pathlib import Path

from app.modules.hardsub_ocr.hardsub_ocr_schema import OCRSubtitleLine
from app.modules.hardsub_ocr.ocr_srt_builder import OCRSRTBuilder


def test_ocr_srt_builder_writes_valid_srt_and_clamps_duration(tmp_path: Path):
    output = tmp_path / "ocr.srt"
    lines = [
        OCRSubtitleLine(index=1, start_ms=0, end_ms=400, text="这个真的很好用", confidence=0.9, frame_count=1),
        OCRSubtitleLine(index=2, start_ms=900, end_ms=2000, text="价格也很便宜", confidence=0.8, frame_count=2),
    ]

    OCRSRTBuilder(min_duration_ms=500).build_srt(lines, str(output), video_duration_ms=1500)

    text = output.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:00,500" in text
    assert "00:00:00,900 --> 00:00:01,500" in text
    assert "这个真的很好用" in text
