from pathlib import Path

from app.modules.queue_control import QueueSettings, ResourceGuardService


def test_resource_guard_service_reports_disk_warning(tmp_path: Path):
    report = ResourceGuardService(str(tmp_path)).check_resources(QueueSettings(min_free_disk_gb=10_000_000))

    assert report["ok"] is False
    assert report["warnings"]
    assert "disk" in str(report["disk"]).lower() or "ổ đĩa" in " ".join(report["warnings"]).lower()
