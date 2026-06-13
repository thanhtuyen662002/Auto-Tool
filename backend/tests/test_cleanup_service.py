from datetime import datetime, timedelta
from pathlib import Path
import os

from app.local_app.data_management.cleanup_service import CleanupService
from app.local_app.data_management.data_management_schema import CleanupRequest, CleanupTarget


def test_cleanup_preview_does_not_delete_file(tmp_path: Path):
    log_dir = tmp_path / "logs" / "launcher"
    log_dir.mkdir(parents=True)
    log_file = log_dir / "old.log"
    log_file.write_text("abc", encoding="utf-8")
    old_time = (datetime.now() - timedelta(days=30)).timestamp()
    os.utime(log_file, (old_time, old_time))

    result = CleanupService(tmp_path).preview_cleanup(
        CleanupRequest(targets=[CleanupTarget.launcher_logs], older_than_days=14)
    )

    assert result.success
    assert result.dry_run
    assert result.preview_items
    assert log_file.exists()


def test_cleanup_run_requires_confirm_delete(tmp_path: Path):
    cache = tmp_path / "cache"
    cache.mkdir()
    file_path = cache / "item.bin"
    file_path.write_bytes(b"abc")

    result = CleanupService(tmp_path).run_cleanup(
        CleanupRequest(targets=[CleanupTarget.cache_files], dry_run=False, confirm_delete=False)
    )

    assert result.dry_run
    assert file_path.exists()
    assert result.warnings


def test_cleanup_run_deletes_confirmed_cache_but_not_final_video(tmp_path: Path):
    cache = tmp_path / "cache"
    cache.mkdir()
    cache_file = cache / "item.bin"
    cache_file.write_bytes(b"abc")
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    video = outputs / "failed_final.mp4"
    video.write_bytes(b"video")

    result = CleanupService(tmp_path).run_cleanup(
        CleanupRequest(
            targets=[CleanupTarget.cache_files, CleanupTarget.failed_partial_renders],
            dry_run=False,
            confirm_delete=True,
        )
    )

    assert result.success
    assert not cache.exists()
    assert video.exists()

