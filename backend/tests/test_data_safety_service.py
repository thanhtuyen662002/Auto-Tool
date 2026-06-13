from pathlib import Path
from zipfile import ZipFile

from app.local_app.data_management.data_management_schema import CleanupTarget
from app.local_app.data_management.data_safety_service import DataSafetyService


def test_data_safety_blocks_zip_slip_and_sensitive_files(tmp_path: Path):
    service = DataSafetyService(tmp_path)

    assert service.prevent_zip_slip("config/local_app_config.json")
    assert not service.prevent_zip_slip("../secret.txt")
    assert not service.prevent_zip_slip("/absolute/path.txt")
    assert not service.prevent_zip_slip("C:/secret.txt")
    assert service.is_sensitive_file(tmp_path / ".env")
    assert service.is_sensitive_file(tmp_path / "credentials.json")
    assert service.is_sensitive_file(tmp_path / "private.pem")


def test_data_safety_does_not_delete_config_or_video(tmp_path: Path):
    service = DataSafetyService(tmp_path)
    config_file = tmp_path / "config" / "local_app_config.json"
    video_file = tmp_path / "outputs" / "job_failed.mp4"
    config_file.parent.mkdir()
    video_file.parent.mkdir()
    config_file.write_text("{}", encoding="utf-8")
    video_file.write_bytes(b"video")

    safe, _ = service.is_safe_to_delete(config_file, CleanupTarget.cache_files)
    assert not safe
    safe, _ = service.is_safe_to_delete(video_file, CleanupTarget.failed_partial_renders)
    assert not safe

