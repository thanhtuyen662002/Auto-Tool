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


def test_merger_salvages_low_confidence_chinese_subtitle_lines():
    settings = DouyinReupSettings(enabled=True, ocr_min_confidence=0.55, ocr_dedupe_similarity=0.86)

    lines = OCRLineMerger().merge_frames_to_lines(
        [
            _frame(0, "陶瓷油的内胆 8。", 0.44),
            _frame(1000, "点也不粘锅 盥", 0.47),
            _frame(2000, "外观颜值高", 0.91),
            _frame(3000, "要问它能手啥", 0.02),
        ],
        settings,
    )

    assert [line.text for line in lines] == ["陶瓷油的内胆 8。", "点也不粘锅 盥", "外观颜值高"]
    assert lines[0].warnings
    assert lines[1].warnings
    assert not lines[2].warnings


def test_merger_merges_ocr_variants_and_keeps_better_text():
    settings = DouyinReupSettings(enabled=True, ocr_min_confidence=0.55, ocr_dedupe_similarity=0.9)

    lines = OCRLineMerger().merge_frames_to_lines(
        [
            _frame(8000, "丽且 点都不粘", 0.46),
            _frame(9000, "而且 点都不粘", 0.82),
        ],
        settings,
    )

    assert len(lines) == 1
    assert lines[0].text == "而且 点都不粘"
    assert lines[0].frame_count == 2


def test_merger_keeps_useful_low_confidence_chinese_candidates():
    settings = DouyinReupSettings(enabled=True, ocr_min_confidence=0.55)

    lines = OCRLineMerger().merge_frames_to_lines(
        [
            _frame(0, "逑介全", confidence=0.0007),
            _frame(1000, "家里一定要有一个好用的电炖锅", confidence=0.03),
        ],
        settings,
    )

    assert [line.text for line in lines] == ["家里一定要有一个好用的电炖锅"]
    assert any("ocr_low_confidence_candidate" in warning for warning in lines[0].warnings)
