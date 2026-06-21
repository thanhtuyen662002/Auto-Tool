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


def test_merger_strips_known_xiaomi_watermark_from_ocr_text():
    settings = DouyinReupSettings(enabled=True, ocr_min_confidence=0.55)
    merger = OCRLineMerger()

    lines = merger.merge_frames_to_lines(
        [
            _frame(0, "\u5c0f\u7c73\u540c\u5b66"),
            _frame(500, "\u5c0f\u7c73\u540c\u5b66 \u8fd9\u4e2a\u771f\u7684\u5f88\u597d\u7528"),
            _frame(1000, "\u5c0f\u7c73\u540c\u5b66 \u8fd9\u4e2a\u771f\u7684\u5f88\u597d\u7528"),
        ],
        settings,
    )

    assert [line.text for line in lines] == ["\u8fd9\u4e2a\u771f\u7684\u5f88\u597d\u7528"]
    assert any("ocr_watermark_filtered" in warning for warning in lines[0].warnings)
    assert merger.last_filter_summary["watermark_removed_frame_count"] == 3
    assert merger.last_filter_summary["watermark_only_frame_count"] == 1


def test_merger_auto_detects_repeated_unknown_prefix_watermark():
    settings = DouyinReupSettings(enabled=True, ocr_min_confidence=0.55, ocr_watermark_terms=[])
    merger = OCRLineMerger()

    lines = merger.merge_frames_to_lines(
        [
            _frame(0, "\u54c1\u724c\u540c\u5b66\u8fd9\u4e2a\u771f\u7684\u5f88\u597d\u7528"),
            _frame(600, "\u54c1\u724c\u540c\u5b66\u4ef7\u683c\u4e5f\u5f88\u4fbf\u5b9c"),
            _frame(1200, "\u54c1\u724c\u540c\u5b66\u5916\u89c2\u989c\u503c\u5f88\u9ad8"),
        ],
        settings,
    )

    assert [line.text for line in lines] == [
        "\u8fd9\u4e2a\u771f\u7684\u5f88\u597d\u7528",
        "\u4ef7\u683c\u4e5f\u5f88\u4fbf\u5b9c",
        "\u5916\u89c2\u989c\u503c\u5f88\u9ad8",
    ]
    assert "\u54c1\u724c\u540c\u5b66" in merger.last_filter_summary["auto_watermark_terms"]
    assert merger.last_filter_summary["watermark_removed_frame_count"] == 3


def test_merger_auto_detects_repeated_raw_block_watermark():
    settings = DouyinReupSettings(enabled=True, ocr_min_confidence=0.55, ocr_watermark_terms=[])
    frames = [
        OCRFrameResult(
            timestamp_ms=index * 600,
            region=OCRRegion(x=0, y=0, width=1080, height=1920),
            text=f"\u5e97\u94fa\u540d {subtitle}",
            confidence=0.9,
            raw_blocks=[
                {
                    "box": [[760, 140], [930, 140], [930, 190], [760, 190]],
                    "text": "\u5e97\u94fa\u540d",
                    "confidence": 0.96,
                },
                {
                    "box": [[150, 1320], [930, 1320], [930, 1390], [150, 1390]],
                    "text": subtitle,
                    "confidence": 0.85,
                },
            ],
        )
        for index, subtitle in enumerate(
            [
                "\u8fd9\u4e2a\u6536\u7eb3\u771f\u7684\u5f88\u65b9\u4fbf",
                "\u4ef7\u683c\u4e5f\u5f88\u4fbf\u5b9c",
                "\u5916\u89c2\u989c\u503c\u5f88\u9ad8",
            ]
        )
    ]
    merger = OCRLineMerger()

    lines = merger.merge_frames_to_lines(frames, settings)

    assert [line.text for line in lines] == [
        "\u8fd9\u4e2a\u6536\u7eb3\u771f\u7684\u5f88\u65b9\u4fbf",
        "\u4ef7\u683c\u4e5f\u5f88\u4fbf\u5b9c",
        "\u5916\u89c2\u989c\u503c\u5f88\u9ad8",
    ]
    assert "\u5e97\u94fa\u540d" in merger.last_filter_summary["auto_watermark_terms"]


def test_merger_uses_subtitle_raw_block_when_watermark_is_separate():
    settings = DouyinReupSettings(enabled=True, ocr_min_confidence=0.55)
    frame = OCRFrameResult(
        timestamp_ms=0,
        region=OCRRegion(x=0, y=0, width=1080, height=1920),
        text="\u5c0f\u7c73\u540c\u5b66 \u8fd9\u4e2a\u6536\u7eb3\u771f\u7684\u5f88\u65b9\u4fbf",
        confidence=0.9,
        raw_blocks=[
            {
                "box": [[780, 100], [980, 100], [980, 150], [780, 150]],
                "text": "\u5c0f\u7c73\u540c\u5b66",
                "confidence": 0.96,
            },
            {
                "box": [[150, 1320], [930, 1320], [930, 1390], [150, 1390]],
                "text": "\u8fd9\u4e2a\u6536\u7eb3\u771f\u7684\u5f88\u65b9\u4fbf",
                "confidence": 0.82,
            },
        ],
    )

    lines = OCRLineMerger().merge_frames_to_lines([frame], settings)

    assert [line.text for line in lines] == ["\u8fd9\u4e2a\u6536\u7eb3\u771f\u7684\u5f88\u65b9\u4fbf"]
