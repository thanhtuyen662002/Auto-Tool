from __future__ import annotations

from app.modules.douyin_reup.douyin_reup_service import _friendly_error


def test_missing_faster_whisper_message_is_actionable():
    message = _friendly_error("No module named faster_whisper")

    assert "faster-whisper" in message
    assert "requirements.txt" in message or "tắt ASR" in message


def test_ffmpeg_error_message_is_not_raw_traceback():
    message = _friendly_error("ffmpeg exited with code 1")

    assert "FFmpeg" in message
    assert "Traceback" not in message
