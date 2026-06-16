from __future__ import annotations

import importlib.util
from types import SimpleNamespace

from app.modules.douyin_reup.asr_service import ASRService, _asr_audio_limit_seconds, _is_missing_vad_asset_error
from app.schemas.media_schema import MediaFile


def test_faster_whisper_dependency_is_available():
    assert importlib.util.find_spec("faster_whisper") is not None


def test_asr_uses_no_vad_by_default_for_better_dialogue_coverage():
    class FakeModel:
        def __init__(self) -> None:
            self.calls: list[bool] = []

        def transcribe(self, audio_path, **kwargs):
            self.calls.append(kwargs["vad_filter"])
            return [SimpleNamespace(start=0.0, end=1.0, text="你好")], None

    service = ASRService()
    model = FakeModel()

    segments = service._transcribe_with_vad_fallback(model, "audio.wav", "zh")

    assert model.calls == [False]
    assert segments[0].text == "你好"


def test_asr_retries_without_vad_when_silero_asset_is_missing():
    class FakeModel:
        def __init__(self) -> None:
            self.calls: list[bool] = []

        def transcribe(self, audio_path, **kwargs):
            self.calls.append(kwargs["vad_filter"])
            if kwargs["vad_filter"]:
                raise RuntimeError(
                    "[ONNXRuntimeError] : 3 : NO_SUCHFILE : "
                    "Load model faster_whisper/assets/silero_vad_v6.onnx failed. File doesn't exist"
                )
            return [SimpleNamespace(start=0.0, end=1.0, text="你好")], None

    service = ASRService()
    model = FakeModel()

    segments = service._transcribe_with_vad_fallback(model, "audio.wav", "zh", vad_filter=True)

    assert model.calls == [True, False]
    assert segments[0].text == "你好"
    assert service.warnings


def test_missing_vad_asset_error_detection():
    assert _is_missing_vad_asset_error(RuntimeError("silero_vad_v6.onnx File doesn't exist"))


def test_asr_audio_limit_caps_long_video_duration(monkeypatch):
    monkeypatch.setenv("AUTO_TOOL_ASR_MAX_AUDIO_SECONDS", "120")
    monkeypatch.setattr(
        "app.modules.douyin_reup.asr_service.probe_video",
        lambda path: MediaFile(
            path=path,
            duration=300,
            width=1080,
            height=1920,
            fps=30,
            has_audio=True,
            format_name="mp4",
        ),
    )

    assert _asr_audio_limit_seconds("long.mp4") == 120


def test_asr_audio_limit_can_be_disabled(monkeypatch):
    monkeypatch.setenv("AUTO_TOOL_ASR_MAX_AUDIO_SECONDS", "0")

    assert _asr_audio_limit_seconds("long.mp4") is None
