import json

from app.tools import silent_mode_v1_rc_test
from backend.tests.silent_v1_rc_test_support import install_fake_flow, make_args, make_config


def test_one_corrupt_video_does_not_crash_whole_batch(tmp_path, monkeypatch):
    config, source, _output = make_config(tmp_path, ["broken.mp4", "good.mp4"])
    install_fake_flow(
        monkeypatch,
        silent_mode_v1_rc_test,
        [source / "broken.mp4", source / "good.mp4"],
        fail_names={"broken.mp4"},
    )

    result = silent_mode_v1_rc_test.run_rc_test(make_args(config, plan_only=True, review_mode=False))

    assert result["status"] == "success_with_warnings"
    assert result["failed"] == 1
    assert result["plans_created"] == 1
    assert result["failure_breakdown"]["visual_segmentation_failed"] == 1


def test_empty_source_has_clear_message_and_writes_summary(tmp_path):
    config, _source, output = make_config(tmp_path, [])

    result = silent_mode_v1_rc_test.run_rc_test(make_args(config, scan_only=True))

    assert result["status"] == "success_with_warnings"
    assert any("No video files found" in warning for warning in result["warnings"])
    summary = json.loads((output / "silent_mode_summary.json").read_text(encoding="utf-8"))
    assert summary["total_videos"] == 0

