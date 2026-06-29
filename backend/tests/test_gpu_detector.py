from __future__ import annotations

from app.utils import gpu_detector


def test_gpu_detector_reports_nvidia_hardware_without_cuda(monkeypatch):
    gpu_detector.detect_gpu_status.cache_clear()
    monkeypatch.setattr(gpu_detector, "_detect_with_nvidia_smi", lambda: ["NVIDIA GeForce RTX 3060 Ti"])
    monkeypatch.setattr(gpu_detector, "_detect_with_windows_cim", lambda: [])
    monkeypatch.setattr(gpu_detector, "_detect_torch_cuda", lambda: (False, None, None))
    monkeypatch.setattr(gpu_detector, "_detect_ctranslate2_cuda", lambda: (False, None))

    status = gpu_detector.detect_gpu_status()

    assert status.hardware_available is True
    assert status.hardware_name == "NVIDIA GeForce RTX 3060 Ti"
    assert status.asr_cuda_available is False
    assert "RTX 3060 Ti" in (status.message or "")
    assert "CPU" in (status.message or "")
    gpu_detector.detect_gpu_status.cache_clear()


def test_gpu_detector_reports_asr_cuda_available(monkeypatch):
    gpu_detector.detect_gpu_status.cache_clear()
    monkeypatch.setattr(gpu_detector, "_detect_with_nvidia_smi", lambda: ["NVIDIA GeForce RTX 3060 Ti"])
    monkeypatch.setattr(gpu_detector, "_detect_with_windows_cim", lambda: [])
    monkeypatch.setattr(gpu_detector, "_detect_torch_cuda", lambda: (False, None, None))
    monkeypatch.setattr(gpu_detector, "_detect_ctranslate2_cuda", lambda: (True, None))

    status = gpu_detector.detect_gpu_status()

    assert status.hardware_available is True
    assert status.cuda_available is True
    assert status.asr_cuda_available is True
    assert "ASR" in (status.message or "")
    gpu_detector.detect_gpu_status.cache_clear()
