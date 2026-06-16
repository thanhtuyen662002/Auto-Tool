from __future__ import annotations

import argparse
import json
import tempfile
import time
from datetime import datetime
from pathlib import Path

from app.modules.queue_control import QueueItemStatus, QueueSettings, QueueState, QueueStateService, QueueWatchdogService


def main() -> int:
    args = _parse_args()
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="autotool_stress_") as tmp:
        root = Path(tmp)
        storage_root = root / "queue"
        output_dir = root / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        video_paths = [str(root / "source" / f"video_{index:05d}.mp4") for index in range(1, args.items + 1)]
        settings = QueueSettings(
            performance_mode=args.performance_mode,
            batch_chunk_size=args.chunk_size,
            watchdog_stale_minutes=1,
            auto_fail_stale_items=args.auto_fail_stale,
            pause_on_repeated_failures=True,
            max_consecutive_failures=args.max_consecutive_failures,
        )
        service = QueueStateService(storage_root=storage_root)
        state = service.create_queue_state(
            args.job_id,
            args.mode,
            video_paths,
            settings,
            str(output_dir),
            project_id="stress-project",
        )

        failed_every = max(0, args.failed_every)
        state = _complete_items_in_chunks(service, state, output_dir, failed_every)

        watchdog = QueueWatchdogService(service).inspect(args.job_id)
        final_state = service.load_queue_state(args.job_id)
        elapsed = time.monotonic() - started
        report = {
            "status": "ok",
            "items": args.items,
            "mode": args.mode,
            "elapsed_seconds": round(elapsed, 3),
            "items_per_second": round(args.items / elapsed, 2) if elapsed > 0 else None,
            "chunk_size": final_state.settings.batch_chunk_size if final_state else None,
            "chunk_count": final_state.concurrency_plan.chunk_count if final_state and final_state.concurrency_plan else None,
            "completed": final_state.completed_items if final_state else 0,
            "failed": final_state.failed_items if final_state else 0,
            "progress_percent": final_state.progress_percent if final_state else 0,
            "watchdog_messages": watchdog.get("messages", []),
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mô phỏng queue batch lớn mà không render video thật.")
    parser.add_argument("--items", type=int, default=1000, help="Số video giả lập.")
    parser.add_argument("--mode", default="douyin_reup", choices=["douyin_reup", "silent_immersive", "product_render"])
    parser.add_argument("--performance-mode", default="safe", choices=["safe", "balanced", "fast"])
    parser.add_argument("--chunk-size", type=int, default=50)
    parser.add_argument("--failed-every", type=int, default=0, help="Cho fail mỗi N item để test summary.")
    parser.add_argument("--max-consecutive-failures", type=int, default=10)
    parser.add_argument("--auto-fail-stale", action="store_true")
    parser.add_argument("--job-id", default="stress-job")
    return parser.parse_args()


def _complete_items_in_chunks(
    service: QueueStateService,
    state: QueueState,
    output_dir: Path,
    failed_every: int,
) -> QueueState:
    chunk_size = max(1, int(state.settings.batch_chunk_size or 1))
    items = list(state.items)
    for chunk_start in range(0, len(items), chunk_size):
        now = datetime.now().replace(microsecond=0).isoformat()
        chunk_end = min(len(items), chunk_start + chunk_size)
        for index in range(chunk_start, chunk_end):
            item = items[index]
            status = QueueItemStatus.failed if failed_every and item.order_index % failed_every == 0 else QueueItemStatus.completed
            items[index] = item.model_copy(
                update={
                    "status": status,
                    "current_step": "stress_completed",
                    "progress_percent": 100,
                    "started_at": item.started_at or now,
                    "completed_at": now,
                    "updated_at": now,
                    "error_message": "Stress test simulated failure" if status == QueueItemStatus.failed else None,
                    "output_video_path": str(output_dir / f"video_{item.order_index:05d}.mp4")
                    if status == QueueItemStatus.completed
                    else None,
                }
            )
        state = service.save_queue_state(
            state.model_copy(
                update={
                    "items": items,
                    "current_step": f"stress_chunk_{(chunk_start // chunk_size) + 1}",
                }
            )
        )
    return state


if __name__ == "__main__":
    raise SystemExit(main())
