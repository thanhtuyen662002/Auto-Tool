import json

from app.tools import silent_mode_v1_rc_test
from backend.tests.silent_v1_rc_test_support import install_fake_flow, make_args, make_config


def test_rc_job_and_video_logs_have_required_contract(tmp_path, monkeypatch):
    config, source, output = make_config(tmp_path, ["clip.mp4"])
    install_fake_flow(monkeypatch, silent_mode_v1_rc_test, [source / "clip.mp4"])

    silent_mode_v1_rc_test.run_rc_test(make_args(config, plan_only=True, review_mode=False))

    job_log = json.loads((output / "job_log.json").read_text(encoding="utf-8"))
    for field in ["version", "mode", "preset_id", "strategy", "industry", "status", "steps", "failed_step", "warnings", "errors", "durations", "paths"]:
        assert field in job_log
    video_dir = next(output.glob("video_*"))
    for name in ["silent_reup_plan.json", "silent_reup_log.json", "visual_tag_report.json", "caption_generation_log.json"]:
        assert (video_dir / name).exists()

