from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.utils.app_paths import app_data_dir


class QueueEventLogger:
    def __init__(self, storage_root: Path | None = None) -> None:
        self.storage_root = (storage_root or app_data_dir() / "data" / "queue_control").resolve()
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def log_event(self, job_id: str, event: str, payload: dict[str, Any] | None = None, output_dir: str | None = None) -> None:
        record = {
            "time": datetime.now().replace(microsecond=0).isoformat(),
            "event": event,
            "job_id": job_id,
            "payload": payload or {},
        }
        for path in [self.storage_root / _safe_name(job_id) / "queue_events.log", _output_log_path(output_dir)]:
            if path is None:
                continue
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as file:
                    file.write(json.dumps(record, ensure_ascii=False) + "\n")
            except OSError:
                continue


def _output_log_path(output_dir: str | None) -> Path | None:
    return Path(output_dir) / "queue_events.log" if output_dir else None


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)[:120] or "job"

