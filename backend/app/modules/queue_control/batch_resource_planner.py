from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from app.modules.queue_control.queue_control_schema import BatchResourcePlan, QueueSettings


class BatchResourcePlanner:
    """Build a conservative concurrency plan for long-running render queues."""

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
        chunk_size = _chunk_size_for(settings, total_items)
        chunk_count = (total_items + chunk_size - 1) // chunk_size if total_items > 0 else 0
        can_use_product_pool = (
            mode == "product_render"
            and total_items > 1
            and settings.allow_parallel_render
            and requested > 1
            and recommended > 1
        )

        warnings: list[str] = []
        if can_use_product_pool:
            effective = min(requested, recommended, 2)
            worker_pool_enabled = True
            execution_mode = "parallel_ready"
            reasons = [
                f"Product render được phép chạy tối đa {effective} video song song trên máy hiện tại.",
                "ASR/OCR/dịch thuật vẫn khóa 1 luồng; worker pool chỉ mở cho bước render product.",
            ]
        else:
            effective = 1
            worker_pool_enabled = False
            execution_mode = "clamped" if requested > 1 else "sequential"
            reasons = [
                "Pipeline hiện tại chạy tuần tự để tránh xung đột ASR/OCR/FFmpeg/TTS trong batch lớn.",
            ]
            if requested > 1 or settings.allow_parallel_asr or settings.allow_parallel_ocr or settings.allow_parallel_render:
                warnings.append(
                    "Đã khóa concurrency hiệu dụng về 1 vì pipeline này chưa đủ điều kiện chạy song song an toàn."
                )
            if recommended > 1:
                reasons.append(
                    f"Máy này có thể chạy tối đa {recommended} worker sau khi pipeline tương ứng được bật an toàn."
                )

        effective_settings = settings.model_copy(
            update={
                "max_concurrent_videos": effective,
                "batch_chunk_size": chunk_size,
            }
        )
        plan = BatchResourcePlan(
            requested_concurrency=requested,
            effective_concurrency=effective,
            recommended_concurrency=recommended,
            worker_pool_enabled=worker_pool_enabled,
            execution_mode=execution_mode,
            mode=mode,
            total_items=total_items,
            chunk_size=chunk_size,
            chunk_count=chunk_count,
            estimated_items_per_hour=_estimated_items_per_hour(mode, effective),
            stage_limits={
                "asr": 1,
                "ocr": 1,
                "render": effective,
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


def _chunk_size_for(settings: QueueSettings, total_items: int) -> int:
    requested = int(settings.batch_chunk_size or 50)
    if settings.performance_mode == "fast":
        default = 100
    elif settings.performance_mode == "balanced":
        default = 50
    else:
        default = 25
    size = requested if requested != 50 else default
    if total_items >= 1000:
        size = min(size, 100)
    return max(1, min(size, 500))


def _estimated_items_per_hour(mode: str, effective_concurrency: int) -> float | None:
    if mode in {"douyin_reup", "silent_immersive"}:
        return round(10.0 * max(1, effective_concurrency), 1)
    if mode == "product_render":
        return round(20.0 * max(1, effective_concurrency), 1)
    return None
