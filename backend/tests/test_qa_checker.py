from __future__ import annotations

import json
from dataclasses import dataclass

from app.modules.qa_checker import qa_checker


@dataclass
class FakeMedia:
    duration: float = 12.1
    width: int = 1080
    height: int = 1920
    has_audio: bool = True


def _write_script(path, text: str = "Một câu subtitle hợp lệ.") -> None:
    path.write_text(
        json.dumps(
            {
                "hook": "Hook",
                "voiceover": [{"time_hint": "0-3s", "text": text}],
                "subtitles": [{"start_hint": 0, "end_hint": 3, "text": text}],
                "cta": "Xem ngay",
                "caption": "Caption",
                "hashtags": ["#test"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_check_output_video_passes_with_valid_files(tmp_path, monkeypatch):
    video_path = tmp_path / "video.mp4"
    subtitle_path = tmp_path / "video.srt"
    script_path = tmp_path / "script.json"
    video_path.write_bytes(b"video")
    subtitle_path.write_text("1\n00:00:00,000 --> 00:00:03,000\nMột câu subtitle.\n", encoding="utf-8")
    _write_script(script_path)
    monkeypatch.setattr(qa_checker, "probe_video", lambda path: FakeMedia())

    result = qa_checker.check_output_video(
        str(video_path),
        expected_duration=12,
        expected_resolution="1080x1920",
        subtitle_path=str(subtitle_path),
        script_path=str(script_path),
    )

    assert result["passed"] is True
    assert result["errors"] == []
    assert result["checks"]["script_schema"]["status"] == "success"


def test_duration_under_two_seconds_is_warning_not_failure(tmp_path, monkeypatch):
    video_path = tmp_path / "video.mp4"
    subtitle_path = tmp_path / "video.srt"
    script_path = tmp_path / "script.json"
    video_path.write_bytes(b"video")
    subtitle_path.write_text("1\n00:00:00,000 --> 00:00:03,000\nMột câu subtitle.\n", encoding="utf-8")
    _write_script(script_path)
    monkeypatch.setattr(qa_checker, "probe_video", lambda path: FakeMedia(duration=13.8))

    result = qa_checker.check_output_video(
        str(video_path),
        expected_duration=12,
        subtitle_path=str(subtitle_path),
        script_path=str(script_path),
    )

    assert result["passed"] is True
    assert result["checks"]["duration"]["status"] == "warning"
    assert result["warnings"]


def test_missing_audio_can_be_warning_for_mock_tts(tmp_path, monkeypatch):
    video_path = tmp_path / "video.mp4"
    subtitle_path = tmp_path / "video.srt"
    script_path = tmp_path / "script.json"
    video_path.write_bytes(b"video")
    subtitle_path.write_text("1\n00:00:00,000 --> 00:00:03,000\nMột câu subtitle.\n", encoding="utf-8")
    _write_script(script_path)
    monkeypatch.setattr(qa_checker, "probe_video", lambda path: FakeMedia(has_audio=False))

    result = qa_checker.check_output_video(
        str(video_path),
        expected_duration=12,
        subtitle_path=str(subtitle_path),
        script_path=str(script_path),
        allow_missing_audio=True,
    )

    assert result["passed"] is True
    assert result["checks"]["audio_stream"]["status"] == "warning"


def test_script_placeholder_fails_output(tmp_path, monkeypatch):
    video_path = tmp_path / "video.mp4"
    subtitle_path = tmp_path / "video.srt"
    script_path = tmp_path / "script.json"
    video_path.write_bytes(b"video")
    subtitle_path.write_text("1\n00:00:00,000 --> 00:00:03,000\nMột câu subtitle.\n", encoding="utf-8")
    _write_script(script_path, text="Đây là {product_name}.")
    monkeypatch.setattr(qa_checker, "probe_video", lambda path: FakeMedia())

    result = qa_checker.check_output_video(
        str(video_path),
        expected_duration=12,
        subtitle_path=str(subtitle_path),
        script_path=str(script_path),
    )

    assert result["passed"] is False
    assert result["checks"]["script_placeholders"]["status"] == "failed"
    assert "{product_name}" in result["errors"][0]
