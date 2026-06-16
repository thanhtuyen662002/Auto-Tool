from __future__ import annotations

import ctypes
import os
from typing import Any


def memory_snapshot() -> dict[str, Any] | None:
    try:
        import psutil  # type: ignore

        memory = psutil.virtual_memory()
        return {
            "memory_available": True,
            "memory_total_gb": round(memory.total / (1024**3), 2),
            "memory_available_gb": round(memory.available / (1024**3), 2),
            "memory_percent": round(float(memory.percent), 1),
        }
    except Exception:
        return _windows_memory_snapshot()


def cpu_percent() -> float | None:
    try:
        import psutil  # type: ignore

        return round(float(psutil.cpu_percent(interval=0)), 1)
    except Exception:
        return None


def _windows_memory_snapshot() -> dict[str, Any] | None:
    if os.name != "nt":
        return None

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
        return None

    total = float(status.ullTotalPhys)
    available = float(status.ullAvailPhys)
    if total <= 0:
        return None
    used_percent = max(0.0, min(100.0, (1.0 - (available / total)) * 100.0))
    return {
        "memory_available": True,
        "memory_total_gb": round(total / (1024**3), 2),
        "memory_available_gb": round(available / (1024**3), 2),
        "memory_percent": round(used_percent, 1),
    }
