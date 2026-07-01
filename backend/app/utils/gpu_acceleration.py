from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.utils.dependency_manager import DependencyError, resolve_tool
from app.utils.gpu_detector import GpuStatus, detect_gpu_status
from app.utils.subprocess_utils import run_hidden


def build_gpu_acceleration_report(ocr_provider: str | None = None) -> dict[str, Any]:
    gpu = detect_gpu_status()
    normalized_provider = _normalize_ocr_provider(ocr_provider)
    nvidia_ready = is_nvidia_gpu(gpu)
    nvenc_available = bool(nvidia_ready and is_nvenc_ready())
    ocr_gpu_available, ocr_mode, ocr_note = _ocr_gpu_status(gpu, normalized_provider)
    status = _overall_status(
        hardware_available=gpu.hardware_available,
        asr_ready=gpu.asr_cuda_available,
        ocr_ready=ocr_gpu_available,
        nvenc_ready=nvenc_available,
    )
    notes: list[str] = []
    if not gpu.hardware_available:
        notes.append("Không phát hiện GPU rời. Tool sẽ chạy CPU như cũ.")
    elif not gpu.cuda_available:
        notes.append("Đã thấy GPU nhưng CUDA runtime chưa sẵn sàng cho ASR/OCR.")
    if nvidia_ready and not nvenc_available:
        notes.append("FFmpeg chưa xác nhận h264_nvenc, render sẽ dùng CPU libx264.")
    if ocr_note:
        notes.append(ocr_note)

    return {
        "status": status,
        "safe_cpu_fallback": True,
        "hardware_available": gpu.hardware_available,
        "hardware_name": gpu.hardware_name,
        "hardware_names": list(gpu.hardware_names),
        "cuda_available": gpu.cuda_available,
        "asr_cuda_available": gpu.asr_cuda_available,
        "torch_cuda_available": gpu.torch_cuda_available,
        "detection_method": gpu.detection_method,
        "ocr_provider": normalized_provider,
        "ocr_gpu_available": ocr_gpu_available,
        "ocr_gpu_mode": ocr_mode,
        "render_nvenc_available": nvenc_available,
        "render_encoder_preferred": "h264_nvenc" if nvenc_available else "libx264",
        "features": [
            {
                "id": "asr",
                "label": "Nghe lời thoại/ASR",
                "available": bool(gpu.asr_cuda_available),
                "engine": "faster-whisper CUDA" if gpu.asr_cuda_available else "CPU fallback",
            },
            {
                "id": "ocr",
                "label": "Đọc chữ trên video/OCR",
                "available": bool(ocr_gpu_available),
                "engine": ocr_mode or "CPU fallback",
            },
            {
                "id": "render",
                "label": "Render/mã hóa video",
                "available": bool(nvenc_available),
                "engine": "h264_nvenc" if nvenc_available else "libx264",
            },
        ],
        "notes": notes,
        "warnings": list(gpu.warnings),
    }


def is_nvidia_gpu(gpu: GpuStatus | None = None) -> bool:
    gpu = gpu or detect_gpu_status()
    names = " ".join(gpu.hardware_names or ((gpu.hardware_name or ""),)).lower()
    return gpu.hardware_available and any(
        token in names for token in ("nvidia", "geforce", "rtx", "gtx", "quadro", "tesla", "cuda")
    )


@lru_cache(maxsize=1)
def is_nvenc_ready() -> bool:
    try:
        ffmpeg_path = resolve_tool("ffmpeg")
    except DependencyError:
        return False
    try:
        result = run_hidden(
            [ffmpeg_path, "-hide_banner", "-encoders"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
        )
    except Exception:
        return False
    if result.returncode != 0:
        return False
    text = f"{result.stdout}\n{result.stderr}".lower()
    return "h264_nvenc" in text


def runtime_gpu_profile(
    settings: Any,
    *,
    subtitle_source: str | None = None,
    render_encoder: str | None = None,
) -> dict[str, Any]:
    report = build_gpu_acceleration_report(getattr(settings, "ocr_provider", None))
    asr_device = str(getattr(settings, "asr_device", "auto") or "auto").lower()
    asr_cuda_ready = bool(report.get("asr_cuda_available"))
    profile = {
        "readiness": report,
        "asr_device": asr_device,
        "asr_cuda_used": bool(
            subtitle_source == "asr"
            and asr_cuda_ready
            and asr_device in {"auto", "cuda"}
        ),
        "ocr_provider": report.get("ocr_provider"),
        "ocr_gpu_ready": bool(report.get("ocr_gpu_available")),
        "subtitle_source": subtitle_source,
        "render_encoder": render_encoder or report.get("render_encoder_preferred") or "libx264",
        "render_nvenc_used": (render_encoder == "h264_nvenc") if render_encoder else False,
        "safe_cpu_fallback": True,
    }
    return profile


def _normalize_ocr_provider(provider: str | None) -> str:
    normalized = (provider or "easyocr").strip().lower()
    if normalized in {"paddle", "paddle_ocr"}:
        return "paddleocr"
    if normalized in {"easy", "easy_ocr"}:
        return "easyocr"
    return normalized or "easyocr"


def _ocr_gpu_status(gpu: GpuStatus, provider: str) -> tuple[bool, str, str | None]:
    if provider == "easyocr":
        if gpu.torch_cuda_available:
            return True, "torch_cuda", None
        if gpu.hardware_available:
            return False, "cpu", "EasyOCR cần GPU khi PyTorch CUDA sẵn sàng."
        return False, "cpu", None
    if provider == "paddleocr":
        if is_nvidia_gpu(gpu):
            return True, "paddle_gpu_candidate", "PaddleOCR sẽ thử GPU trước và tự fallback CPU nếu thiếu paddlepaddle-gpu."
        return False, "cpu", None
    if provider == "mock_ocr":
        return False, "mock", "Mock OCR chỉ dùng để thử nghiệm, không dùng GPU."
    return False, "cpu", None


def _overall_status(
    *,
    hardware_available: bool,
    asr_ready: bool,
    ocr_ready: bool,
    nvenc_ready: bool,
) -> str:
    if not hardware_available:
        return "cpu_only"
    ready_count = sum(1 for value in (asr_ready, ocr_ready, nvenc_ready) if value)
    if ready_count >= 2:
        return "gpu_ready"
    if ready_count == 1:
        return "partial_gpu"
    return "gpu_detected_runtime_missing"
