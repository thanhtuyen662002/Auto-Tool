from __future__ import annotations

from app.modules.silent_immersive_reup.speech_presence_detector import SpeechPresenceDetector
from app.schemas.media_schema import MediaFile


def test_asr_detection_runs_automatically_for_suspicious_audio(monkeypatch):
    monkeypatch.delenv("AUTO_TOOL_SILENT_SPEECH_ASR", raising=False)
    detector = SpeechPresenceDetector()
    assert detector._should_run_asr(0.4) is True
    assert detector._should_run_asr(0.05) is False


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


def test_asr_without_segments_recommends_silent_mode(monkeypatch):
    monkeypatch.setattr(
        "app.modules.silent_immersive_reup.speech_presence_detector.probe_video",
        lambda path: MediaFile(path=path, duration=8, width=1080, height=1920, fps=30, has_audio=True, format_name="mp4"),
    )
    monkeypatch.setattr(SpeechPresenceDetector, "_audio_energy_score", staticmethod(lambda *_args, **_kwargs: 0.6))
    monkeypatch.setattr(SpeechPresenceDetector, "_asr_segment_count", staticmethod(lambda _path: 0))

    result = SpeechPresenceDetector(enable_asr=True).detect("clip.mp4")

    assert result.has_speech is False
    assert result.speech_segments_count == 0
    assert result.method == "asr_fast_detect"


def test_audio_energy_only_is_not_treated_as_confirmed_speech(monkeypatch):
    monkeypatch.setattr(
        "app.modules.silent_immersive_reup.speech_presence_detector.probe_video",
        lambda path: MediaFile(path=path, duration=8, width=1080, height=1920, fps=30, has_audio=True, format_name="mp4"),
    )
    monkeypatch.setattr(SpeechPresenceDetector, "_audio_energy_score", staticmethod(lambda *_args, **_kwargs: 1.0))

    result = SpeechPresenceDetector(enable_asr=False).detect("clip.mp4")

    assert result.has_speech is False
    assert result.speech_score == 0
    assert result.audio_energy_score == 1.0
    assert result.method == "audio_energy_heuristic"


def test_asr_failure_keeps_video_in_silent_mode(monkeypatch):
    monkeypatch.setattr(
        "app.modules.silent_immersive_reup.speech_presence_detector.probe_video",
        lambda path: MediaFile(path=path, duration=8, width=1080, height=1920, fps=30, has_audio=True, format_name="mp4"),
    )
    monkeypatch.setattr(SpeechPresenceDetector, "_audio_energy_score", staticmethod(lambda *_args, **_kwargs: 1.0))
    monkeypatch.setattr(SpeechPresenceDetector, "_asr_segment_count", staticmethod(lambda _path: (_ for _ in ()).throw(RuntimeError("boom"))))

    result = SpeechPresenceDetector(enable_asr=True).detect("clip.mp4")

    assert result.has_speech is False
    assert result.speech_score == 0
    assert result.method == "asr_unavailable"


def test_asr_with_multiple_segments_detects_speech(monkeypatch):
    monkeypatch.setattr(
        "app.modules.silent_immersive_reup.speech_presence_detector.probe_video",
        lambda path: MediaFile(path=path, duration=8, width=1080, height=1920, fps=30, has_audio=True, format_name="mp4"),
    )
    monkeypatch.setattr(SpeechPresenceDetector, "_audio_energy_score", staticmethod(lambda *_args, **_kwargs: 0.3))
    monkeypatch.setattr(SpeechPresenceDetector, "_asr_segment_count", staticmethod(lambda _path: 2))

    result = SpeechPresenceDetector(enable_asr=True).detect("clip.mp4")

    assert result.has_speech is True
    assert result.speech_score == 0.5
