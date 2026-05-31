from __future__ import annotations

from app.modules.tts.text_cleanup import clean_text_for_tts, estimate_voice_duration


def test_clean_text_removes_markdown_hashtag_emoji_and_labels():
    text = "Hook: **Máy chiếu này ổn lắm** 😄 #review\nCTA: Xem ngay!"

    cleaned = clean_text_for_tts(text)

    assert cleaned == "Máy chiếu này ổn lắm Xem ngay!"
    assert "#review" not in cleaned
    assert "😄" not in cleaned
    assert "Hook:" not in cleaned
    assert "CTA:" not in cleaned


def test_estimate_voice_duration_uses_vietnamese_reading_speed():
    assert estimate_voice_duration("Xin chào mọi người", "vi") > 1.0
