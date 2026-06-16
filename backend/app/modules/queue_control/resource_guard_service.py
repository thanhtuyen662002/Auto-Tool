from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from app.modules.queue_control.queue_control_schema import QueueSettings
from app.modules.queue_control.system_resources import cpu_percent, memory_snapshot


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
        warnings = []
        cpu = cpu_percent()
        memory = memory_snapshot()
        memory_percent = float(memory["memory_percent"]) if memory and "memory_percent" in memory else None

        if cpu is not None and cpu >= settings.max_cpu_percent_warning:
            warnings.append(f"CPU đang cao: {cpu:.1f}%, ngưỡng cảnh báo {settings.max_cpu_percent_warning:.1f}%.")
        if memory_percent is not None and memory_percent >= settings.max_memory_percent_warning:
            warnings.append(f"RAM đang cao: {memory_percent:.1f}%, ngưỡng cảnh báo {settings.max_memory_percent_warning:.1f}%.")

        return {
            "available": bool(cpu is not None or memory),
            "cpu_percent": cpu,
            "memory_percent": memory_percent,
            "memory_total_gb": memory.get("memory_total_gb") if memory else None,
            "memory_available_gb": memory.get("memory_available_gb") if memory else None,
            "warnings": warnings,
        }
