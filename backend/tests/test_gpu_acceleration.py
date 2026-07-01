from __future__ import annotations

from app.utils import gpu_acceleration
from app.utils.gpu_detector import GpuStatus


def test_gpu_acceleration_report_keeps_cpu_only_safe(monkeypatch):
    monkeypatch.setattr(
        gpu_acceleration,
        "detect_gpu_status",
        lambda: GpuStatus(hardware_available=False, message="CPU only"),
    )

    report = gpu_acceleration.build_gpu_acceleration_report("easyocr")

    assert report["status"] == "cpu_only"
    assert report["safe_cpu_fallback"] is True
    assert report["render_encoder_preferred"] == "libx264"
    assert report["render_nvenc_available"] is False
    assert report["ocr_gpu_available"] is False


def test_gpu_acceleration_report_detects_nvenc_and_cuda_paths(monkeypatch):
    monkeypatch.setattr(
        gpu_acceleration,
        "detect_gpu_status",
        lambda: GpuStatus(
            hardware_available=True,
            hardware_name="NVIDIA GeForce RTX 3060 Ti",
            hardware_names=("NVIDIA GeForce RTX 3060 Ti",),
            cuda_available=True,
            asr_cuda_available=True,
            torch_cuda_available=True,
        ),
    )
    monkeypatch.setattr(gpu_acceleration, "is_nvenc_ready", lambda: True)

    report = gpu_acceleration.build_gpu_acceleration_report("easyocr")

    assert report["status"] == "gpu_ready"
    assert report["asr_cuda_available"] is True
    assert report["ocr_gpu_available"] is True
    assert report["render_nvenc_available"] is True
    assert report["render_encoder_preferred"] == "h264_nvenc"


def test_runtime_profile_counts_auto_asr_as_cuda_when_ready(monkeypatch):
    monkeypatch.setattr(
        gpu_acceleration,
        "detect_gpu_status",
        lambda: GpuStatus(
            hardware_available=True,
            hardware_name="NVIDIA GeForce RTX 3060 Ti",
            hardware_names=("NVIDIA GeForce RTX 3060 Ti",),
            cuda_available=True,
            asr_cuda_available=True,
            torch_cuda_available=False,
        ),
    )
    monkeypatch.setattr(gpu_acceleration, "is_nvenc_ready", lambda: False)

    class Settings:
        asr_device = "auto"
        ocr_provider = "paddleocr"

    profile = gpu_acceleration.runtime_gpu_profile(Settings(), subtitle_source="asr")

    assert profile["asr_cuda_used"] is True
    assert profile["safe_cpu_fallback"] is True
