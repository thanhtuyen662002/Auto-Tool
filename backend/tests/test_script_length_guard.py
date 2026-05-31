from __future__ import annotations

from app.modules.script_writer.length_guard import prepare_script_for_tts
from app.modules.script_writer.script_writer import ProductVideoScript
from app.modules.tts.text_cleanup import estimate_voice_duration


def _script_with_long_voiceover() -> ProductVideoScript:
    long_line = (
        "Đây là một câu mô tả rất dài về sản phẩm, lặp lại nhiều ý không cần thiết "
        "và khiến phần voiceover dài hơn nhiều so với video ngắn. "
    )
    return ProductVideoScript.model_validate(
        {
            "hook": "Hook sản phẩm",
            "voiceover": [
                {"time_hint": "", "text": "Hook: Sản phẩm này đáng xem #review"},
                {"time_hint": "", "text": long_line * 6},
                {"time_hint": "", "text": "Thiết kế gọn và dễ dùng."},
                {"time_hint": "", "text": "Phù hợp nhiều nhu cầu hằng ngày."},
                {"time_hint": "", "text": "Xem chi tiết sản phẩm ngay"},
            ],
            "subtitles": [{"text": "Sản phẩm này đáng xem"}],
            "cta": "Xem chi tiết sản phẩm ngay",
            "caption": "Caption không được đưa vào voiceover",
            "hashtags": ["#review"],
        }
    )


def test_script_too_long_is_shortened_before_tts():
    script = _script_with_long_voiceover()

    shortened, warnings = prepare_script_for_tts(script, target_duration=6.0, language="vi")

    assert warnings
    assert len(shortened.voiceover) < len(script.voiceover)
    assert "Xem chi tiết sản phẩm ngay" in " ".join(line.text for line in shortened.voiceover)
    assert estimate_voice_duration(" ".join(line.text for line in shortened.voiceover), "vi") <= 8.0


def test_caption_is_not_included_in_voiceover():
    shortened, _ = prepare_script_for_tts(_script_with_long_voiceover(), target_duration=20.0, language="vi")

    assert "Caption không được đưa vào voiceover" not in " ".join(line.text for line in shortened.voiceover)
