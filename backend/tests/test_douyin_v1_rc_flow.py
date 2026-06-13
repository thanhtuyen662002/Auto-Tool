from __future__ import annotations

import json
from pathlib import Path

from app.tools.douyin_reup_v1_rc_test import build_parser, run_rc_test
from app.version import APP_VERSION


def test_v1_rc_command_returns_success_with_warnings_for_empty_dataset(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    config = tmp_path / "v1_safe_review.json"
    config.write_text(
        json.dumps(
            {
                "project_name": "rc-empty",
                "source_folder": str(source),
                "output_folder": str(output),
                "douyin_reup": {"preset_id": "safe_review"},
            }
        ),
        encoding="utf-8",
    )
    args = build_parser().parse_args(["--config", str(config), "--mock-asr", "--mock-ocr", "--mock-translation"])

    result = run_rc_test(args)

    assert result["version"] == APP_VERSION
    assert result["status"] == "success_with_warnings"
    assert result["scanned"] == 0
    assert "No video files found" in result["warnings"][0]


def test_v1_rc_command_supports_scan_only(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    config = tmp_path / "v1_safe_review.json"
    config.write_text(
        json.dumps(
            {
                "project_name": "rc-scan-only",
                "source_folder": str(source),
                "output_folder": str(output),
            }
        ),
        encoding="utf-8",
    )
    args = build_parser().parse_args(["--config", str(config), "--scan-only"])

    result = run_rc_test(args)

    assert result["status"] == "success_with_warnings"
    assert result["source_srt_created"] == 0
