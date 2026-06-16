from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from app.modules.queue_control.queue_control_schema import BatchResourcePlan, QueueSettings


class BatchResourcePlanner:
    """Builds a truthful concurrency plan for long-running render queues.

    The current render engines are stateful and execute one video at a time.
    This planner records that fact explicitly while still computing a future
    worker-pool recommendation from machine resources.
    """

    def build_plan(
        self,
        *,
        mode: str,
        settings: QueueSettings,
        output_dir: str | None,
        total_items: int,
    ) -> tuple[QueueSettings, BatchResourcePlan]:
        resources = self._resource_snapshot(output_dir)
        requested = max(1, int(settings.max_concurrent_videos))
        recommended = self._recommended_concurrency(resources)
        reasons = [
            "Engine render hiện tại vẫn chạy tuần tự để tránh xung đột ASR/OCR/FFmpeg/TTS trong batch lớn.",
        ]
        warnings: list[str] = []
        if requested > 1 or settings.allow_parallel_asr or settings.allow_parallel_ocr or settings.allow_parallel_render:
            warnings.append(
                "Đã khóa concurrency hiệu dụng về 1 vì worker pool song song chưa được bật an toàn cho pipeline hiện tại."
            )
        if recommended > 1:
            reasons.append(
                f"Máy này có thể là ứng viên cho worker pool tối đa {recommended} video song song sau khi bật scheduler an toàn."
            )

        effective_settings = settings.model_copy(update={"max_concurrent_videos": 1})
        plan = BatchResourcePlan(
            requested_concurrency=requested,
            effective_concurrency=1,
            recommended_concurrency=recommended,
            worker_pool_enabled=False,
            execution_mode="clamped" if requested > 1 else "sequential",
            mode=mode,
            total_items=total_items,
            stage_limits={
                "asr": 1,
                "ocr": 1,
                "render": 1,
                "tts": 1,
                "translation": 1,
            },
            resources=resources,
            reasons=reasons,
            warnings=warnings,
        )
        return effective_settings, plan

    def _resource_snapshot(self, output_dir: str | None) -> dict[str, Any]:
        path = Path(output_dir or Path.cwd())
        if not path.exists():
            path = Path.cwd()
        disk = shutil.disk_usage(path)
        snapshot: dict[str, Any] = {
            "cpu_count": os.cpu_count() or 1,
            "disk_free_gb": round(disk.free / (1024**3), 2),
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "memory_available": False,
        }
        try:
            import psutil  # type: ignore

            memory = psutil.virtual_memory()
            snapshot.update(
                {
                    "memory_available": True,
                    "memory_total_gb": round(memory.total / (1024**3), 2),
                    "memory_available_gb": round(memory.available / (1024**3), 2),
                    "memory_percent": round(float(memory.percent), 1),
                    "cpu_percent": round(float(psutil.cpu_percent(interval=0)), 1),
                }
            )
        except Exception:
            pass
        return snapshot

    def _recommended_concurrency(self, resources: dict[str, Any]) -> int:
        cpu_count = int(resources.get("cpu_count") or 1)
        disk_free_gb = float(resources.get("disk_free_gb") or 0.0)
        memory_total_gb = float(resources.get("memory_total_gb") or 0.0)
        memory_available_gb = float(resources.get("memory_available_gb") or 0.0)
        if cpu_count >= 8 and disk_free_gb >= 20 and (not resources.get("memory_available") or memory_total_gb >= 16):
            if not resources.get("memory_available") or memory_available_gb >= 8:
                return 2
        return 1
