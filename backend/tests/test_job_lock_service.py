from datetime import datetime, timedelta
from pathlib import Path

from app.modules.job_recovery.job_lock_service import JobLockService


def test_job_lock_prevents_double_resume(tmp_path: Path):
    service = JobLockService(tmp_path / "locks")

    assert service.acquire_job_lock("job-1") is True
    assert service.acquire_job_lock("job-1") is False

    service.release_job_lock("job-1")
    assert service.acquire_job_lock("job-1") is True


def test_stale_lock_cleanup(tmp_path: Path):
    service = JobLockService(tmp_path / "locks", stale_hours=1)
    assert service.acquire_job_lock("job-old") is True
    lock_path = service._lock_path("job-old")
    old = datetime.now() - timedelta(hours=2)
    lock_path.write_text(
        f'{{"job_id":"job-old","pid":999999,"created_at":"{old.replace(microsecond=0).isoformat()}"}}',
        encoding="utf-8",
    )

    assert service.cleanup_stale_lock("job-old") is True
    assert service.is_job_locked("job-old") is False

