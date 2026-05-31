from __future__ import annotations

from pathlib import Path

from app.modules.script_writer.script_writer import ProductVideoScript
from app.modules.subtitle_generator.subtitle_generator import SubtitleGenerator


def _script() -> ProductVideoScript:
    return ProductVideoScript.model_validate(
        {
            "hook": "Hook",
            "voiceover": [
                {"time_hint": "0-4s", "text": "Câu một hoàn chỉnh."},
                {"time_hint": "4-8s", "text": "Câu hai hoàn chỉnh."},
            ],
            "subtitles": [
                {"start_hint": 0, "end_hint": 4, "text": "Câu một hoàn chỉnh."},
                {"start_hint": 4, "end_hint": 8, "text": "Câu hai hoàn chỉnh."},
            ],
            "cta": "Xem ngay",
            "caption": "Caption",
            "hashtags": [],
        }
    )


def test_voice_shorter_than_video_clamps_subtitle_active_duration(tmp_path):
    output = tmp_path / "short.srt"
    generator = SubtitleGenerator()

    generator.generate_srt(_script(), target_video_duration=10.0, voice_duration=5.0, output_path=str(output))

    assert "voice_shorter_than_video" in generator.warnings
    assert generator.last_active_duration == 5.0
    assert "00:00:05,000" in output.read_text(encoding="utf-8")


def test_voice_longer_than_video_does_not_exceed_video_duration(tmp_path):
    output = tmp_path / "long.srt"
    generator = SubtitleGenerator()

    generator.generate_srt(_script(), target_video_duration=8.0, voice_duration=12.0, output_path=str(output))

    content = Path(output).read_text(encoding="utf-8")
    assert "voice_longer_than_video" in generator.warnings
    assert generator.last_active_duration == 7.9
    assert "00:00:08,000" not in content
    assert "00:00:07,900" in content
