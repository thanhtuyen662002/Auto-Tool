from __future__ import annotations

import json
from pathlib import Path

from app import database
from app.modules.output_review.review_schema import OutputReviewStatus
from app.modules.output_review.review_service import OutputQualityReviewService


def test_success_output_gets_high_quality_score(tmp_path):
    project_id, output_dir = _seed_project_with_outputs(tmp_path, [_success_output(tmp_path, 1)])

    scores = OutputQualityReviewService().analyze_project_outputs(project_id)

    assert len(scores) == 1
    assert scores[0].overall_score >= 0.85
    assert scores[0].recommended_action == "good"
    assert (output_dir / "output_quality_review.json").exists()


def test_failed_output_recommends_rerender_failed(tmp_path):
    project_id, _ = _seed_project_with_outputs(tmp_path, [_failed_output(tmp_path, 2)])

    score = OutputQualityReviewService().analyze_output(project_id, 2)

    assert score.technical_score == 0.0
    assert score.recommended_action == "rerender_failed"
    assert score.errors


def test_silent_fallback_lowers_audio_score(tmp_path):
    output = _success_output(tmp_path, 1)
    log_path = Path(output["log_file"])
    log_payload = json.loads(log_path.read_text(encoding="utf-8"))
    log_payload["tts_provider"] = "silent"
    log_payload["tts"]["provider_used"] = "silent"
    log_path.write_text(json.dumps(log_payload), encoding="utf-8")
    project_id, _ = _seed_project_with_outputs(tmp_path, [output])

    score = OutputQualityReviewService().analyze_output(project_id, 1)

    assert score.audio_score == 0.3
    assert score.overall_score < 0.9


def test_manual_review_status_is_preserved_after_reanalysis(tmp_path):
    project_id, _ = _seed_project_with_outputs(tmp_path, [_success_output(tmp_path, 1)])
    OutputQualityReviewService().analyze_project_outputs(project_id)
    database.update_output_review(project_id, 1, OutputReviewStatus.needs_rerender.value, "Subtitle late")

    OutputQualityReviewService().analyze_project_outputs(project_id)
    review = database.get_output_review(project_id, 1)

    assert review is not None
    assert review["review_status"] == OutputReviewStatus.needs_rerender.value
    assert review["user_note"] == "Subtitle late"


def _seed_project_with_outputs(tmp_path: Path, outputs: list[dict]) -> tuple[str, Path]:
    database.DB_PATH = tmp_path / "autotool-test.db"
    database.init_db()
    project_id = "project-1"
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)
    database.create_project(project_id, _config(source_dir, output_dir))
    database.create_job("job-1", project_id, preview_only=False, total_outputs=len(outputs))
    database.update_job(
        "job-1",
        status="completed",
        output_folder=str(output_dir),
        results_json=json.dumps({"outputs": outputs}, ensure_ascii=False),
    )
    return project_id, output_dir


def _success_output(tmp_path: Path, index: int) -> dict:
    output_dir = tmp_path / "outputs"
    output_dir.mkdir(exist_ok=True)
    final_path = output_dir / f"video_{index:03d}.mp4"
    final_path.write_bytes(b"not-real-video-but-qa-log-is-authoritative")
    subtitle_path = output_dir / f"video_{index:03d}_sub.ass"
    subtitle_path.write_text("subtitle", encoding="utf-8")
    timeline_path = output_dir / f"video_{index:03d}_timeline.json"
    timeline_path.write_text(
        json.dumps(
            {
                "output_index": index,
                "template_id": "ugc_reviewer_natural",
                "target_duration": 12,
                "average_segment_score": 0.9,
                "source_diversity": {"unique_sources": 2, "total_clips": 3},
                "clips": [
                    {"source_path": "a.mp4", "slot_name": "hook", "text_role": "hook", "segment_score": 0.9},
                    {"source_path": "b.mp4", "slot_name": "demo", "text_role": "benefit", "segment_score": 0.9},
                    {"source_path": "a.mp4", "slot_name": "cta", "text_role": "cta", "segment_score": 0.9},
                ],
            }
        ),
        encoding="utf-8",
    )
    log_path = output_dir / f"video_{index:03d}_log.json"
    log_payload = {
        "index": index,
        "status": "success",
        "final_video": str(final_path),
        "subtitle_ass_file": str(subtitle_path),
        "timeline_file": str(timeline_path),
        "tts_provider": "edge_tts",
        "tts_fallback_used": False,
        "voice_duration": 12.1,
        "tts": {"provider_used": "edge_tts", "fallback_used": False, "voice_duration": 12.1, "warnings": []},
        "qa": {
            "exists": True,
            "probe_ok": True,
            "duration_ok": True,
            "resolution_ok": True,
            "has_video_stream": True,
            "has_audio_stream": True,
            "warnings": [],
            "errors": [],
        },
        "warnings": [],
        "errors": [],
    }
    log_path.write_text(json.dumps(log_payload), encoding="utf-8")
    return {
        "index": index,
        "path": str(final_path),
        "status": "success",
        "subtitle_ass_file": str(subtitle_path),
        "timeline_file": str(timeline_path),
        "log_file": str(log_path),
        "tts_provider": "edge_tts",
        "tts_fallback_used": False,
        "warnings": [],
        "errors": [],
    }


def _failed_output(tmp_path: Path, index: int) -> dict:
    output_dir = tmp_path / "outputs"
    output_dir.mkdir(exist_ok=True)
    final_path = output_dir / f"video_{index:03d}.mp4"
    log_path = output_dir / f"video_{index:03d}_log.json"
    message = "render_final failed: FFmpeg render failed"
    log_path.write_text(
        json.dumps({"index": index, "status": "failed", "warnings": [], "errors": [message]}),
        encoding="utf-8",
    )
    return {
        "index": index,
        "path": str(final_path),
        "status": "failed",
        "error": message,
        "warnings": [],
        "errors": [message],
        "log_file": str(log_path),
    }


def _config(source_dir: Path, output_dir: Path) -> dict:
    return {
        "project_name": "review-test",
        "source_folder": str(source_dir),
        "output_folder": str(output_dir),
        "product": {
            "name": "Product",
            "brand": "Brand",
            "description": "Description",
            "features": ["Feature"],
            "cta": "CTA",
        },
        "render": {
            "output_count": 2,
            "duration": 12,
            "aspect_ratio": "9:16",
            "resolution": "1080x1920",
            "fps": 30,
        },
        "effects": {
            "cut_intensity": 70,
            "speed_variation": 30,
            "grain": 0,
            "zoom_motion": 0,
            "overlay_height": 33,
            "subtitle_size": 84,
        },
        "ai": {
            "text_model": "gemini-test",
            "tone": "friendly_reviewer",
            "language": "vi",
            "gemini_api_keys": [],
        },
        "music": {
            "enabled": False,
            "source_folder": None,
            "source_file": None,
            "volume": 0.12,
            "fade_in": 0.5,
            "fade_out": 0.8,
            "duck_under_voice": False,
        },
    }
