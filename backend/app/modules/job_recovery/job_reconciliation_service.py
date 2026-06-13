from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app import database
from app.adapters.ffmpeg_adapter import FFmpegError, probe_video


class JobReconciliationService:
    def reconcile_job_outputs(self, job_id: str) -> dict[str, Any]:
        job = database.get_job(job_id)
        if not job:
            raise LookupError(f"Không tìm thấy job: {job_id}")
        outputs = list((job.get("results") or {}).get("outputs") or [])
        reconciled: list[dict[str, Any]] = []
        completed = 0
        failed = 0
        interrupted = 0
        warnings: list[str] = []
        for output in outputs:
            if not isinstance(output, dict):
                continue
            item = dict(output)
            path = str(item.get("path") or "")
            expected_type = "video" if path.lower().endswith((".mp4", ".mov", ".mkv", ".webm", ".avi")) else "file"
            valid = self.check_output_exists_and_valid(path, expected_type) if path else False
            item["reconciled_output_exists"] = valid
            if valid and item.get("status") in {"success", "warning", "rendered", "qa_checked"}:
                completed += 1
                item["recovery_status"] = "rendered"
            elif valid:
                completed += 1
                item["recovery_status"] = "rendered"
                warnings.append(f"Output tồn tại nhưng status không phải success: {path}")
            elif item.get("status") == "failed":
                failed += 1
                item["recovery_status"] = "failed"
            else:
                interrupted += 1
                item["recovery_status"] = "interrupted"
            reconciled.append(item)

        total = int(job.get("total_outputs") or len(reconciled))
        if total > len(reconciled):
            interrupted += total - len(reconciled)
        result = {
            "job_id": job_id,
            "total_items": total,
            "completed_items": completed,
            "failed_items": failed,
            "interrupted_items": interrupted,
            "outputs": reconciled,
            "warnings": warnings,
        }
        self._write_reconciliation(job, result)
        return result

    def check_output_exists_and_valid(self, path: str, expected_type: str) -> bool:
        if not path:
            return False
        target = Path(path).expanduser()
        if not target.exists() or not target.is_file() or target.stat().st_size <= 0:
            return False
        if expected_type == "video":
            try:
                media = probe_video(str(target))
                return media.duration > 0 and media.width > 0 and media.height > 0
            except (FFmpegError, OSError, ValueError):
                return False
        return True

    def rebuild_summary_from_checkpoints(self, job_id: str) -> dict[str, Any]:
        reconciliation = self.reconcile_job_outputs(job_id)
        return {
            "job_id": job_id,
            "total_outputs": reconciliation["total_items"],
            "successful_outputs": reconciliation["completed_items"],
            "failed_outputs": reconciliation["failed_items"],
            "interrupted_outputs": reconciliation["interrupted_items"],
            "outputs": reconciliation["outputs"],
        }

    def _write_reconciliation(self, job: dict[str, Any], result: dict[str, Any]) -> None:
        output_folder = job.get("output_folder")
        if not output_folder:
            return
        try:
            path = Path(output_folder) / "recovery_reconciliation.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            return

