from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.utils.subprocess_utils import run_hidden


@dataclass(frozen=True)
class GpuStatus:
    hardware_available: bool = False
    hardware_name: str | None = None
    hardware_names: tuple[str, ...] = ()
    cuda_available: bool = False
    asr_cuda_available: bool = False
    torch_cuda_available: bool = False
    detection_method: str | None = None
    message: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)


@lru_cache(maxsize=1)
def detect_gpu_status() -> GpuStatus:
    hardware_names: list[str] = []
    methods: list[str] = []
    warnings: list[str] = []

    nvidia_smi_names = _detect_with_nvidia_smi()
    if nvidia_smi_names:
        hardware_names.extend(nvidia_smi_names)
        methods.append("nvidia-smi")

    cim_names = _detect_with_windows_cim()
    if cim_names:
        _extend_unique(hardware_names, cim_names)
        methods.append("windows-cim")

    torch_available, torch_name, torch_warning = _detect_torch_cuda()
    if torch_name:
        _extend_unique(hardware_names, [torch_name])
    if torch_available and "torch" not in methods:
        methods.append("torch")
    if torch_warning:
        warnings.append(torch_warning)

    asr_cuda_available, asr_warning = _detect_ctranslate2_cuda()
    if asr_cuda_available and not hardware_names:
        hardware_names.append("NVIDIA CUDA GPU")
    if asr_cuda_available and "ctranslate2" not in methods:
        methods.append("ctranslate2")
    if asr_warning:
        warnings.append(asr_warning)

    hardware_names = _dedupe(hardware_names)
    hardware_available = bool(hardware_names)
    cuda_available = bool(torch_available or asr_cuda_available)
    message = _build_gpu_message(
        hardware_available=hardware_available,
        hardware_name=hardware_names[0] if hardware_names else None,
        cuda_available=cuda_available,
        asr_cuda_available=asr_cuda_available,
    )
    return GpuStatus(
        hardware_available=hardware_available,
        hardware_name=hardware_names[0] if hardware_names else None,
        hardware_names=tuple(hardware_names),
        cuda_available=cuda_available,
        asr_cuda_available=asr_cuda_available,
        torch_cuda_available=torch_available,
        detection_method="+".join(methods) if methods else None,
        message=message,
        warnings=tuple(_dedupe(warnings)),
    )


def _detect_with_nvidia_smi() -> list[str]:
    candidates = _nvidia_smi_candidates()
    for candidate in candidates:
        try:
            result = run_hidden(
                [
                    str(candidate),
                    "--query-gpu=name",
                    "--format=csv,noheader",
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=4,
            )
        except OSError:
            continue
        except Exception:
            continue
        if result.returncode != 0:
            continue
        names = _clean_gpu_names(result.stdout.splitlines())
        if names:
            return names
    return []


def _nvidia_smi_candidates() -> list[Path]:
    candidates: list[Path] = []
    found = shutil.which("nvidia-smi")
    if found:
        candidates.append(Path(found))
    for env_name in ("ProgramFiles", "ProgramW6432"):
        root = os.environ.get(env_name)
        if root:
            candidates.append(Path(root) / "NVIDIA Corporation" / "NVSMI" / "nvidia-smi.exe")
    return [candidate for candidate in _dedupe_paths(candidates) if candidate.exists()]


def _detect_with_windows_cim() -> list[str]:
    if os.name != "nt":
        return []
    powershell = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    if not powershell:
        return []
    try:
        result = run_hidden(
            [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                "Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name }",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
    except Exception:
        return []
    if result.returncode != 0:
        return []
    return _clean_gpu_names(result.stdout.splitlines())


def _detect_torch_cuda() -> tuple[bool, str | None, str | None]:
    try:
        import torch  # noqa: PLC0415

        if not torch.cuda.is_available():
            return False, None, None
        name = str(torch.cuda.get_device_name(0) or "").strip() or "CUDA GPU"
        return True, name, None
    except Exception as exc:
        return False, None, f"Không kiểm tra được CUDA qua PyTorch: {_short_error(exc)}"


def _detect_ctranslate2_cuda() -> tuple[bool, str | None]:
    try:
        import ctranslate2  # noqa: PLC0415

        return int(ctranslate2.get_cuda_device_count() or 0) > 0, None
    except Exception as exc:
        return False, f"Không kiểm tra được CUDA cho ASR: {_short_error(exc)}"


def _clean_gpu_names(lines: list[str]) -> list[str]:
    names: list[str] = []
    for line in lines:
        name = " ".join(str(line).strip().split())
        if not name:
            continue
        lowered = name.lower()
        if "microsoft basic" in lowered or "remote display" in lowered:
            continue
        if any(token in lowered for token in ("nvidia", "geforce", "rtx", "gtx", "quadro", "tesla", "radeon", "amd", "intel arc")):
            names.append(name)
    return _dedupe(names)


def _build_gpu_message(
    *,
    hardware_available: bool,
    hardware_name: str | None,
    cuda_available: bool,
    asr_cuda_available: bool,
) -> str:
    if not hardware_available:
        return "Chưa phát hiện GPU rời trên máy này."
    name = hardware_name or "GPU"
    if asr_cuda_available:
        return f"Đã phát hiện {name}; ASR có thể dùng CUDA."
    if cuda_available:
        return f"Đã phát hiện {name}; CUDA có sẵn nhưng ASR chưa xác nhận dùng được GPU."
    return f"Đã phát hiện {name}, nhưng runtime CUDA cho ASR/OCR chưa sẵn sàng nên tool có thể tạm chạy CPU."


def _extend_unique(values: list[str], additions: list[str]) -> None:
    seen = {value.strip().lower() for value in values}
    for value in additions:
        key = value.strip().lower()
        if key and key not in seen:
            values.append(value)
            seen.add(key)


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(str(value).strip().split())
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        result.append(cleaned)
        seen.add(key)
    return result


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path).lower()
        if key in seen:
            continue
        result.append(path)
        seen.add(key)
    return result


def _short_error(exc: Exception) -> str:
    text = str(exc).splitlines()[0].strip()
    return text[:160] if len(text) > 160 else text
