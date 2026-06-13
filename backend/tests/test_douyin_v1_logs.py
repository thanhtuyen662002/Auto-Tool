from __future__ import annotations

import json
from pathlib import Path

from app.tools.douyin_reup_v1_rc_test import build_parser, run_rc_test
from app.version import APP_VERSION


def test_v1_rc_command_writes_job_log_and_summary(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    config = tmp_path / "v1_safe_review.json"
    config.write_text(
        json.dumps({"project_name": "rc-logs", "source_folder": str(source), "output_folder": str(output)}),
        encoding="utf-8",
    )
    args = build_parser().parse_args(["--config", str(config)])

    result = run_rc_test(args)

    job_log = output / "job_log.json"
    summary = output / "douyin_reup_summary.json"
    assert result["status"] == "success_with_warnings"
    assert job_log.exists()
    assert summary.exists()
    assert json.loads(job_log.read_text(encoding="utf-8"))["version"] == APP_VERSION
    assert json.loads(summary.read_text(encoding="utf-8"))["version"] == APP_VERSION
