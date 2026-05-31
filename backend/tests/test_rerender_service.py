from __future__ import annotations

import json
from pathlib import Path

from app import database
from app.modules.output_review.review_schema import OutputReviewStatus
from app.modules.output_review.review_service import OutputQualityReviewService
from app.modules.output_review.rerender_service import RerenderService


def test_rerender_service_resolves_failed_and_manual_needs_rerender(tmp_path):
    project_id = _seed_project(tmp_path)
    OutputQualityReviewService().analyze_project_outputs(project_id)
    database.update_output_review(project_id, 2, OutputReviewStatus.needs_rerender.value, None)

    service = RerenderService()

    assert service.resolve_output_indexes(project_id, "failed_only") == [1]
    assert service.resolve_output_indexes(project_id, "needs_rerender") == [2]
    assert service.resolve_output_indexes(project_id, "selected", [2]) == [2]


def _seed_project(tmp_path: Path) -> str:
    database.DB_PATH = tmp_path / "rerender-service.db"
    database.init_db()
    project_id = "project-rerender"
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir()
    output_dir.mkdir()
    database.create_project(project_id, _config(source_dir, output_dir))
    outputs = [_failed_output(output_dir, 1), _warning_output(output_dir, 2)]
    database.create_job("job-rerender-source", project_id, preview_only=False, total_outputs=2)
    database.update_job(
        "job-rerender-source",
        status="completed_with_errors",
        output_folder=str(output_dir),
        results_json=json.dumps({"outputs": outputs}, ensure_ascii=False),
    )
    return project_id


def _failed_output(output_dir: Path, index: int) -> dict:
    log_path = output_dir / f"video_{index:03d}_log.json"
    error = "render_final failed"
    log_path.write_text(json.dumps({"status": "failed", "errors": [error], "warnings": []}), encoding="utf-8")
    return {
        "index": index,
        "path": str(output_dir / f"video_{index:03d}.mp4"),
        "status": "failed",
        "error": error,
        "errors": [error],
        "warnings": [],
        "log_file": str(log_path),
    }


def _warning_output(output_dir: Path, index: int) -> dict:
    final_path = output_dir / f"video_{index:03d}.mp4"
    final_path.write_bytes(b"video")
    subtitle_path = output_dir / f"video_{index:03d}_sub.ass"
    subtitle_path.write_text("subtitle", encoding="utf-8")
    timeline_path = output_dir / f"video_{index:03d}_timeline.json"
    timeline_path.write_text(
        json.dumps(
            {
                "output_index": index,
                "template_id": "ugc_reviewer_natural",
                "target_duration": 12,
                "average_segment_score": 0.8,
                "source_diversity": {"unique_sources": 1, "total_clips": 2},
                "clips": [
                    {"source_path": "a.mp4", "slot_name": "hook", "text_role": "hook"},
                    {"source_path": "a.mp4", "slot_name": "cta", "text_role": "cta"},
                ],
            }
        ),
        encoding="utf-8",
    )
    log_path = output_dir / f"video_{index:03d}_log.json"
    log_path.write_text(
        json.dumps(
            {
                "status": "warning",
                "subtitle_ass_file": str(subtitle_path),
                "timeline_file": str(timeline_path),
                "tts_provider": "edge_tts",
                "tts": {"provider_used": "edge_tts", "fallback_used": False, "voice_duration": 12, "warnings": []},
                "qa": {
                    "exists": True,
                    "probe_ok": True,
                    "duration_ok": True,
                    "resolution_ok": True,
                    "has_video_stream": True,
                    "has_audio_stream": True,
                    "warnings": ["Voice shorter than video"],
                    "errors": [],
                },
                "warnings": ["Voice shorter than video"],
                "errors": [],
            }
        ),
        encoding="utf-8",
    )
    return {
        "index": index,
        "path": str(final_path),
        "status": "warning",
        "subtitle_ass_file": str(subtitle_path),
        "timeline_file": str(timeline_path),
        "log_file": str(log_path),
        "warnings": ["Voice shorter than video"],
        "errors": [],
    }


def _config(source_dir: Path, output_dir: Path) -> dict:
    return {
        "project_name": "rerender-test",
        "source_folder": str(source_dir),
        "output_folder": str(output_dir),
        "product": {"name": "Product", "brand": "Brand", "description": "Description", "features": ["Feature"], "cta": "CTA"},
        "render": {"output_count": 2, "duration": 12, "aspect_ratio": "9:16", "resolution": "1080x1920", "fps": 30},
        "effects": {"cut_intensity": 70, "speed_variation": 30, "grain": 0, "zoom_motion": 0, "overlay_height": 33, "subtitle_size": 84},
        "ai": {"text_model": "gemini-test", "tone": "friendly_reviewer", "language": "vi", "gemini_api_keys": []},
        "music": {"enabled": False, "source_folder": None, "source_file": None, "volume": 0.12, "fade_in": 0.5, "fade_out": 0.8, "duck_under_voice": False},
    }
