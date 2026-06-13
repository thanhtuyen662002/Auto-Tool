from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from app.utils.app_paths import app_data_dir


class JobLockService:
    def __init__(self, lock_root: Path | None = None, stale_hours: int = 6) -> None:
        self.lock_root = (lock_root or app_data_dir() / "data" / "job_locks").resolve()
        self.lock_root.mkdir(parents=True, exist_ok=True)
        self.stale_hours = stale_hours

    def acquire_job_lock(self, job_id: str) -> bool:
        path = self._lock_path(job_id)
        if self.is_job_locked(job_id):
            return False
        payload = {
            "job_id": job_id,
            "pid": os.getpid(),
            "created_at": datetime.now().replace(microsecond=0).isoformat(),
        }
        temp = path.with_suffix(".lock.tmp")
        try:
            temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(path)
            return True
        except OSError:
            return False

    def release_job_lock(self, job_id: str) -> None:
        try:
            self._lock_path(job_id).unlink(missing_ok=True)
        except OSError:
            return

    def is_job_locked(self, job_id: str) -> bool:
        path = self._lock_path(job_id)
        if not path.exists():
            return False
        payload = self._read_lock(path)
        if self._is_stale(path, payload):
            self.release_job_lock(job_id)
            return False
        return True

    def cleanup_stale_lock(self, job_id: str) -> bool:
        path = self._lock_path(job_id)
        if not path.exists():
            return False
        payload = self._read_lock(path)
        if self._is_stale(path, payload):
            self.release_job_lock(job_id)
            return True
        return False

    def _lock_path(self, job_id: str) -> Path:
        safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in job_id)[:120] or "job"
        return self.lock_root / f"{safe}.lock"

    def _read_lock(self, path: Path) -> dict:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _is_stale(self, path: Path, payload: dict) -> bool:
        created_at = payload.get("created_at")
        try:
            created = datetime.fromisoformat(str(created_at)) if created_at else datetime.fromtimestamp(path.stat().st_mtime)
        except (OSError, ValueError):
            return True
        if datetime.now() - created > timedelta(hours=self.stale_hours):
            return True
        return False

