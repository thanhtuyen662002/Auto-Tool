from __future__ import annotations

from pathlib import Path

from app.config import load_project_config
from app.modules.render_worker.render_worker import render_project

from tests.e2e.helpers import (
    assert_no_placeholder,
    load_json,
    patch_fast_tts,
    source_run_lengths,
    write_project_config,
)


def test_full_batch_pipeline_creates_distinct_scripts_and_logs(tmp_path, monkeypatch):
    patch_fast_tts(monkeypatch)
    config_path = write_project_config(tmp_path, output_count=3, duration=4.0, source_count=4)
    config = load_project_config(str(config_path))

    summary = render_project(config, preview_only=False)

    output_dir = Path(summary["output_folder"])
    assert summary["requested_outputs"] == 3
    assert len(summary["outputs"]) == 3
    assert summary["failed_outputs"] == 0

    project_files = [
        "project_summary.json",
        "segment_scoring_report.json",
        "script_variants.json",
    ]
    for filename in project_files:
        assert (output_dir / filename).exists(), filename

    hooks: set[str] = set()
    for index in range(1, 4):
        name = f"video_{index:03d}"
        for suffix in [".mp4", "_script.json", "_sub.srt", "_voice.wav", "_timeline.json", "_log.json"]:
            path = output_dir / f"{name}{suffix}"
            assert path.exists(), path.name
            assert path.stat().st_size > 0, path.name

        script = load_json(output_dir / f"{name}_script.json")
        hooks.add(script["hook"])
        assert script["voiceover"]
        assert script["subtitles"]
        assert isinstance(script["hashtags"], list)
        assert_no_placeholder(script)

        timeline = load_json(output_dir / f"{name}_timeline.json")
        assert timeline["template_id"] == "ugc_reviewer_natural"
        assert all(clip.get("slot_name") or clip.get("text_role") for clip in timeline["clips"])
        assert max(source_run_lengths(timeline), default=0) <= 2

        output_log = load_json(output_dir / f"{name}_log.json")
        assert output_log["timeline_template"] == "ugc_reviewer_natural"
        assert "average_segment_score" in output_log
        assert output_log["source_diversity"]["unique_sources"] >= 1

    variants = load_json(output_dir / "script_variants.json")
    assert variants["total_variants"] == 3
    assert len({variant["hook"] for variant in variants["variants"]}) > 1
    assert len(hooks) > 1

    persisted_summary = load_json(output_dir / "project_summary.json")
    assert persisted_summary["successful_outputs"] == 3
    assert persisted_summary["failed_outputs"] == 0


def test_full_batch_continues_when_one_output_fails(tmp_path, monkeypatch):
    patch_fast_tts(monkeypatch, fail_pattern=r"video_001")
    config_path = write_project_config(tmp_path, output_count=2, duration=4.0, source_count=3)
    config = load_project_config(str(config_path))

    summary = render_project(config, preview_only=False)

    output_dir = Path(summary["output_folder"])
    assert len(summary["outputs"]) == 2
    assert summary["failed_outputs"] == 1
    assert summary["successful_outputs"] == 1
    assert summary["failed_items"]
    assert "generate_voice" in summary["failed_items"][0]["reason"]

    failed_log = load_json(output_dir / "video_001_log.json")
    assert failed_log["status"] == "failed"
    assert any(step["name"] == "generate_voice" and step["status"] == "failed" for step in failed_log["steps"])

    second_output = summary["outputs"][1]
    assert second_output["status"] in {"success", "warning"}
    assert Path(second_output["path"]).exists()
    assert (output_dir / "video_002_log.json").exists()
    assert (output_dir / "project_summary.json").exists()
