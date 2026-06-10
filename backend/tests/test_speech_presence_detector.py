from __future__ import annotations

from app.modules.silent_immersive_reup.speech_presence_detector import SpeechPresenceDetector
from app.schemas.media_schema import MediaFile


def test_video_without_audio_is_silent(monkeypatch):
    monkeypatch.setattr(
        "app.modules.silent_immersive_reup.speech_presence_detector.probe_video",
        lambda path: MediaFile(
            path=path,
            duration=8,
            width=1080,
            height=1920,
            fps=30,
            has_audio=False,
            format_name="mov,mp4",
        ),
    )

    result = SpeechPresenceDetector().detect("clip.mp4")

    assert result.has_speech is False
    assert result.speech_score == 0
    assert result.method == "no_audio"
