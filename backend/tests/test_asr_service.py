from __future__ import annotations

import importlib.util
import threading
from pathlib import Path
from types import SimpleNamespace

from app.modules.douyin_reup import asr_service
from app.modules.douyin_reup.asr_service import ASRService, _asr_audio_limit_seconds, _is_missing_vad_asset_error
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings
from app.schemas.media_schema import MediaFile
from app.utils.gpu_detector import GpuStatus


CHINESE_HELLO = "\u4f60\u597d"


def test_faster_whisper_dependency_is_available():
    assert importlib.util.find_spec("faster_whisper") is not None


def test_asr_uses_hallucination_guard_options():
    class FakeModel:
        def __init__(self) -> None:
            self.calls: list[bool] = []
            self.kwargs = None

        def transcribe(self, audio_path, **kwargs):
            self.calls.append(kwargs["vad_filter"])
            self.kwargs = kwargs
            return [SimpleNamespace(start=0.0, end=1.0, text=CHINESE_HELLO)], None

    service = ASRService()
    model = FakeModel()

    segments = service._transcribe_with_vad_fallback(model, "audio.wav", "zh")

    assert model.calls == [False]
    assert segments[0].text == CHINESE_HELLO
    assert model.kwargs["condition_on_previous_text"] is False
    assert model.kwargs["no_speech_threshold"] == 0.6
    assert model.kwargs["log_prob_threshold"] == -1.0
    assert model.kwargs["compression_ratio_threshold"] == 2.4


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
            return [SimpleNamespace(start=0.0, end=1.0, text=CHINESE_HELLO)], None

    service = ASRService()
    model = FakeModel()

    segments = service._transcribe_with_vad_fallback(model, "audio.wav", "zh", vad_filter=True)

    assert model.calls == [True, False]
    assert segments[0].text == CHINESE_HELLO
    assert service.warnings


def test_asr_retries_without_vad_when_vad_returns_no_segments(tmp_path, monkeypatch):
    class FakeModel:
        def __init__(self) -> None:
            self.calls: list[bool] = []

        def transcribe(self, audio_path, **kwargs):
            self.calls.append(kwargs["vad_filter"])
            if kwargs["vad_filter"]:
                return [], None
            return [SimpleNamespace(start=0.0, end=1.0, text=CHINESE_HELLO)], None

    output = tmp_path / "asr.srt"
    audio_outputs: list[Path] = []

    def fake_run_ffmpeg(args):
        audio_path = Path(args[-1])
        audio_path.write_bytes(b"wav")
        audio_outputs.append(audio_path)

    model = FakeModel()
    monkeypatch.setattr("app.modules.douyin_reup.asr_service.run_ffmpeg", fake_run_ffmpeg)
    ASRService._model_cache = {("tiny", "cpu"): (model, threading.Lock())}

    try:
        result = ASRService().transcribe_to_srt(
            "video.mp4",
            str(output),
            language="zh",
            model_size="tiny",
            device="cpu",
            vad_filter=True,
            max_audio_seconds=0,
        )
    finally:
        ASRService._model_cache = {}

    assert result == str(output)
    assert model.calls == [True, False]
    assert CHINESE_HELLO in output.read_text(encoding="utf-8")
    assert audio_outputs


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


def test_asr_audio_limit_prefers_explicit_setting(monkeypatch):
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

    assert _asr_audio_limit_seconds("long.mp4", max_audio_seconds=60) == 60


def test_asr_audio_limit_can_be_disabled(monkeypatch):
    monkeypatch.setenv("AUTO_TOOL_ASR_MAX_AUDIO_SECONDS", "0")

    assert _asr_audio_limit_seconds("long.mp4") is None


def test_asr_warning_distinguishes_gpu_hardware_from_cuda_runtime(monkeypatch):
    monkeypatch.setattr(asr_service, "_GPU_AVAILABLE", None)
    monkeypatch.setattr(
        asr_service,
        "detect_gpu_status",
        lambda: GpuStatus(
            hardware_available=True,
            hardware_name="NVIDIA GeForce RTX 3060 Ti",
            hardware_names=("NVIDIA GeForce RTX 3060 Ti",),
            cuda_available=False,
            asr_cuda_available=False,
        ),
    )
    settings = DouyinReupSettings(enabled=True, use_asr_if_no_subtitle=True, asr_device="auto")

    warnings = asr_service.check_asr_support_and_optimize_settings(settings)

    assert settings.asr_device == "cpu"
    assert any("RTX 3060 Ti" in warning for warning in warnings)
    assert all("Chưa phát hiện GPU" not in warning for warning in warnings)


def test_asr_auto_uses_cuda_when_ctranslate2_cuda_is_ready(monkeypatch):
    monkeypatch.setattr(asr_service, "_GPU_AVAILABLE", None)
    monkeypatch.setattr(
        asr_service,
        "detect_gpu_status",
        lambda: GpuStatus(
            hardware_available=True,
            hardware_name="NVIDIA GeForce RTX 3060 Ti",
            hardware_names=("NVIDIA GeForce RTX 3060 Ti",),
            cuda_available=True,
            asr_cuda_available=True,
        ),
    )
    settings = DouyinReupSettings(enabled=True, use_asr_if_no_subtitle=True, asr_device="auto")

    warnings = asr_service.check_asr_support_and_optimize_settings(settings)

    assert settings.asr_device == "cuda"
    assert warnings == []
