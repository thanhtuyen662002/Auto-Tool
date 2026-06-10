from __future__ import annotations

from pathlib import Path

from app.modules.douyin_reup.douyin_schema import DouyinOutputResult, DouyinReupSettings
from app.modules.douyin_reup.douyin_summary_builder import build_douyin_reup_summary
from app.schemas.project_schema import ProjectConfig


def _config(tmp_path: Path) -> ProjectConfig:
    return ProjectConfig.model_validate(
        {
            "project_name": "summary-test",
            "source_folder": str(tmp_path),
            "output_folder": str(tmp_path / "out"),
            "product": {"name": "x", "brand": "", "description": "x", "features": ["x"], "cta": "x"},
            "render": {"output_count": 1, "duration": 8, "aspect_ratio": "9:16", "resolution": "1080x1920", "fps": 30},
            "effects": {"cut_intensity": 0, "speed_variation": 0, "grain": 0, "zoom_motion": 0, "overlay_height": 22, "subtitle_size": 54},
            "ai": {"text_model": "mock", "tone": "translator", "language": "vi", "gemini_api_keys": []},
            "douyin_reup": DouyinReupSettings(enabled=True).model_dump(mode="json"),
        }
    )


def test_douyin_summary_counts_review_render_failure_and_performance(tmp_path: Path):
    outputs = [
        DouyinOutputResult(index=1, path="", status="needs_review", source_video="a.mp4", subtitle_source="sidecar_srt", subtitle_review_document_id="doc-1"),
        DouyinOutputResult(index=2, path="b.mp4", status="success", source_video="b.mp4", subtitle_source="asr", durations={"asr_seconds": 4, "translation_seconds": 1, "render_seconds": 9}),
        DouyinOutputResult(index=3, path="", status="failed", source_video="c.mp4", subtitle_source="asr", failed_step="translation", error_message="bad", errors=["bad"]),
    ]

    summary = build_douyin_reup_summary(
        config=_config(tmp_path),
        output_root=tmp_path / "out",
        outputs=outputs,
        scan_seconds=1.25,
        total_runtime_seconds=20,
    ).model_dump(mode="json")

    assert summary["success"] == 2
    assert summary["failed"] == 1
    assert summary["needs_review"] == 1
    assert summary["rendered"] == 1
    assert summary["failure_breakdown"] == {"translation_failed": 1}
    assert summary["performance"]["slowest_step"] == "render"
