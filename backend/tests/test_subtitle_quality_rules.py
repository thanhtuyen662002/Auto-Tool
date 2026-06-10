from app.modules.subtitle_quality.subtitle_quality_rules import evaluate_line_quality


def _types(**overrides):
    payload = {
        "source_text": "这是测试字幕",
        "text": "Đây là phụ đề kiểm thử.",
        "duration_ms": 2000,
        "line_count": 1,
        "chars_per_second": 10,
        "current_end_ms": 2000,
    }
    payload.update(overrides)
    return {issue.issue_type.value: issue.severity.value for issue in evaluate_line_quality(**payload)}


def test_long_empty_chinese_and_reading_speed_rules():
    assert _types(text="a" * 60)["too_long"] == "warning"
    assert _types(text="a" * 80)["too_long"] == "critical"
    assert _types(text="")["empty_translation"] == "critical"
    assert _types(text="还有中文内容")["untranslated_chinese"] == "critical"
    assert _types(chars_per_second=20)["reading_speed_too_high"] == "warning"
    assert _types(chars_per_second=25)["reading_speed_too_high"] == "critical"


def test_confidence_markdown_and_overlap_rules():
    assert _types(source_text=None, ocr_confidence=0.5)["ocr_low_confidence"] == "warning"
    assert _types(source_text=None, text='{"translation": "abc"}')["markdown_or_json_leak"] == "warning"
    assert _types(next_start_ms=1500)["timestamp_overlap"] == "warning"
