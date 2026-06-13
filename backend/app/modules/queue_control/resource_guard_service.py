from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from app.modules.queue_control.queue_control_schema import QueueSettings


class ResourceGuardService:
    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or Path.cwd())

    def check_resources(self, settings: QueueSettings) -> dict[str, Any]:
        disk = self.check_disk_space(settings.min_free_disk_gb)
        memory_cpu = self.check_memory_cpu(settings)
        warnings = []
        if disk.get("warning"):
            warnings.append(str(disk["warning"]))
        warnings.extend(memory_cpu.get("warnings", []))
        return {
            "disk": disk,
            "memory_cpu": memory_cpu,
            "warnings": warnings,
            "ok": not warnings,
        }

    def should_warn_before_next_item(self, settings: QueueSettings) -> tuple[bool, list[str]]:
        if not settings.resource_guard_enabled:
            return False, []
        report = self.check_resources(settings)
        return bool(report["warnings"]), list(report["warnings"])

    def check_disk_space(self, min_free_disk_gb: float) -> dict[str, Any]:
        usage = shutil.disk_usage(self.path if self.path.exists() else Path.cwd())
        free_gb = round(usage.free / (1024**3), 2)
        total_gb = round(usage.total / (1024**3), 2)
        warning = None
        if free_gb < min_free_disk_gb:
            warning = f"Dung lượng ổ đĩa thấp: còn {free_gb} GB, yêu cầu tối thiểu {min_free_disk_gb} GB."
        return {"free_gb": free_gb, "total_gb": total_gb, "min_free_disk_gb": min_free_disk_gb, "warning": warning}

    def check_memory_cpu(self, settings: QueueSettings) -> dict[str, Any]:
        try:
            import psutil  # type: ignore
        except ImportError:
            return {"available": False, "warnings": []}
        warnings = []
        cpu = float(psutil.cpu_percent(interval=0))
        memory = float(psutil.virtual_memory().percent)
        if cpu >= settings.max_cpu_percent_warning:
            warnings.append(f"CPU đang cao: {cpu:.1f}%, ngưỡng cảnh báo {settings.max_cpu_percent_warning:.1f}%.")
        if memory >= settings.max_memory_percent_warning:
            warnings.append(f"RAM đang cao: {memory:.1f}%, ngưỡng cảnh báo {settings.max_memory_percent_warning:.1f}%.")
        return {"available": True, "cpu_percent": cpu, "memory_percent": memory, "warnings": warnings}
