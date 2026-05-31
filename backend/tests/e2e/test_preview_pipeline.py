from __future__ import annotations

from pathlib import Path

from app.config import load_project_config
from app.modules.render_worker.render_worker import render_project

from tests.e2e.helpers import (
    assert_no_placeholder,
    load_json,
    patch_fast_tts,
    write_project_config,
)


def test_preview_pipeline_creates_expected_files(tmp_path, monkeypatch):
    patch_fast_tts(monkeypatch)
    config_path = write_project_config(tmp_path, output_count=3, duration=4.0, source_count=3)

    config = load_project_config(str(config_path))
    assert Path(config.source_folder).exists()
    assert config.script_variation.mode == "auto_mix"

    summary = render_project(config, preview_only=True)

    output_dir = Path(summary["output_folder"])
    assert output_dir.name == "preview"
    assert summary["requested_outputs"] == 1
    assert summary["total_input_videos"] == 3
    assert summary["total_segments"] > 0
    assert summary["failed_outputs"] == 0

    required_files = [
        "preview_001.mp4",
        "preview_001_visual.mp4",
        "preview_001_script.json",
        "preview_001_sub.srt",
        "preview_001_sub.ass",
        "preview_001_voice.wav",
        "preview_001_timeline.json",
        "preview_001_log.json",
        "segment_scoring_report.json",
        "script_variants.json",
        "project_summary.json",
    ]
    for filename in required_files:
        path = output_dir / filename
        assert path.exists(), filename
        assert path.stat().st_size > 0, filename

    output = summary["outputs"][0]
    assert output["status"] in {"success", "warning"}
    assert Path(output["path"]).exists()

    script = load_json(output_dir / "preview_001_script.json")
    assert script["hook"]
    assert script["voiceover"]
    assert script["subtitles"]
    assert isinstance(script["hashtags"], list)
    assert_no_placeholder(script)

    timeline = load_json(output_dir / "preview_001_timeline.json")
    assert timeline["template_id"] == "ugc_reviewer_natural"
    assert timeline["clips"]
    assert all(clip.get("slot_name") or clip.get("text_role") for clip in timeline["clips"])

    output_log = load_json(output_dir / "preview_001_log.json")
    step_names = {step["name"] for step in output_log["steps"]}
    assert {
        "write_timeline_report",
        "render_visual",
        "generate_script",
        "generate_voice",
        "generate_subtitle",
        "render_final",
        "qa_check",
    }.issubset(step_names)
    assert output_log["average_segment_score"] >= 0
    assert output_log["source_diversity"]["total_clips"] == len(timeline["clips"])
