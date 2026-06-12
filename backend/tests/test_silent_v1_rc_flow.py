from pathlib import Path
from enum import Enum

from app.tools import silent_mode_v1_rc_test
from backend.tests.silent_v1_rc_test_support import install_fake_flow, make_args, make_config


def test_silent_chill_rc_creates_plan_tags_captions_and_review(tmp_path, monkeypatch):
    config, source, output = make_config(tmp_path, ["clip.mp4"])
    install_fake_flow(monkeypatch, silent_mode_v1_rc_test, [source / "clip.mp4"])

    result = silent_mode_v1_rc_test.run_rc_test(make_args(config))

    assert result["status"] in {"success", "success_with_warnings"}
    assert result["plans_created"] == 1
    assert result["visual_tag_reports_created"] == 1
    assert result["captions_generated"] == 1
    assert result["review_documents_created"] == 1
    assert (output / "silent_mode_summary.json").exists()


def test_product_voiceover_rc_creates_script(tmp_path, monkeypatch):
    config, source, output = make_config(tmp_path, ["voice.mp4"])
    install_fake_flow(monkeypatch, silent_mode_v1_rc_test, [source / "voice.mp4"])
    args = make_args(config, preset="silent_product_voiceover", plan_only=True, review_mode=False)

    result = silent_mode_v1_rc_test.run_rc_test(args)

    assert result["plans_created"] == 1
    assert next(output.glob("video_*/voiceover_script.txt")).exists()


def test_final_qa_status_accepts_string_and_enum():
    class Status(str, Enum):
        passed = "passed"

    assert silent_mode_v1_rc_test._qa_status("passed") == "passed"
    assert silent_mode_v1_rc_test._qa_status(Status.passed) == "passed"
