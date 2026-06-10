from __future__ import annotations

from app.modules.douyin_reup.douyin_schema import DouyinReupSettings
from app.modules.hardsub_ocr.hardsub_ocr_schema import OCRFrameResult, OCRRegion
from app.modules.hardsub_ocr.ocr_line_merger import OCRLineMerger


REGION = OCRRegion(x=0, y=100, width=100, height=50)


def _frame(timestamp_ms: int, text: str, confidence: float = 0.9) -> OCRFrameResult:
    return OCRFrameResult(timestamp_ms=timestamp_ms, region=REGION, text=text, confidence=confidence)


def test_merger_groups_duplicate_frames_into_one_line():
    settings = DouyinReupSettings(enabled=True, ocr_min_confidence=0.55, ocr_dedupe_similarity=0.86)

    lines = OCRLineMerger().merge_frames_to_lines(
        [_frame(0, "这个真的很好用"), _frame(500, "这个真的很好用"), _frame(1000, "这个真的很好用")],
        settings,
    )

    assert len(lines) == 1
    assert lines[0].frame_count == 3
    assert lines[0].end_ms >= 1500


def test_merger_splits_when_text_changes():
    settings = DouyinReupSettings(enabled=True, ocr_min_confidence=0.55, ocr_dedupe_similarity=0.9)

    lines = OCRLineMerger().merge_frames_to_lines(
        [_frame(0, "这个真的很好用"), _frame(600, "价格也很便宜")],
        settings,
    )

    assert [line.text for line in lines] == ["这个真的很好用", "价格也很便宜"]
