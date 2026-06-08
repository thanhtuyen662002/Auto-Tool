from __future__ import annotations

from pathlib import Path

import pytest

from app.tools.v02_smoke_test import run_v02_smoke_test
from app.utils.dependency_manager import ensure_runtime_dependencies
from tests.e2e.helpers import write_project_config


def test_v02_smoke_flow_preview_skip_tts_online_creates_content_plan(tmp_path: Path) -> None:
    report = ensure_runtime_dependencies(auto_install=False)
    if not report.ffmpeg_path or not report.ffprobe_path:
        pytest.skip("FFmpeg/ffprobe are required for v0.2 smoke flow rendering.")

    config_path = write_project_config(tmp_path, output_count=3, duration=4.0, source_count=3)
    result = run_v02_smoke_test(config_path, preview_only=True, skip_tts_online=True)

    assert result["status"] in {"success", "success_with_warnings"}
    assert result["steps"]["environment"] == "ok"
    assert result["steps"]["preview_render"] in {"ok", "warning"}
    assert result["steps"]["content_export"] == "ok"
    assert Path(result["preview_path"]).exists()
    assert Path(result["output_folder"], "project_summary.json").exists()
    assert Path(result["content_export_files"]["md"]).exists()
    assert "Traceback (most recent call last)" not in str(result)
