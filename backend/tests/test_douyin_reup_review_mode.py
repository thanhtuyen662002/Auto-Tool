from __future__ import annotations

import shutil
from pathlib import Path

from app import database
from app.modules.douyin_reup.douyin_reup_service import DouyinReupService
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, DouyinVideoItem, SubtitleSourceResult, TranslationResult
from app.modules.subtitle_review import SubtitleReviewService
from app.schemas.project_schema import ProjectConfig


def _project_config(source_folder: Path, output_folder: Path) -> ProjectConfig:
    return ProjectConfig.model_validate(
        {
            "project_name": "douyin-review-test",
            "source_folder": str(source_folder),
            "output_folder": str(output_folder),
            "product": {
                "name": "Douyin",
                "brand": "",
                "description": "Test",
                "features": ["Test"],
                "cta": "Xem",
            },
            "render": {"output_count": 1, "duration": 8, "aspect_ratio": "9:16", "resolution": "1080x1920", "fps": 30},
            "effects": {
                "cut_intensity": 0,
                "speed_variation": 0,
                "grain": 0,
                "zoom_motion": 0,
                "overlay_height": 22,
                "subtitle_size": 54,
            },
            "ai": {"text_model": "gemini-test", "tone": "translator", "language": "vi", "gemini_api_keys": []},
            "douyin_reup": DouyinReupSettings(enabled=True).model_dump(mode="json"),
        }
    )


def test_douyin_review_mode_creates_document_and_skips_render(tmp_path: Path, monkeypatch):
    database.DB_PATH = tmp_path / "autotool-douyin-review.db"
    monkeypatch.setattr("app.modules.subtitle_review.subtitle_review_service._duration_ms", lambda _path: None)
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir()
    video_path = source_dir / "clip.mp4"
    source_srt = source_dir / "clip.srt"
    video_path.write_bytes(b"fake video")
    source_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nNi hao\n", encoding="utf-8")

    class FakeScanner:
        def scan_folder(self, folder):
            return [
                DouyinVideoItem(
                    path=str(video_path),
                    filename=video_path.name,
                    duration=8,
                    width=1080,
                    height=1920,
                    fps=30,
                    has_audio=True,
                    sidecar_srt_path=str(source_srt),
                    embedded_subtitle_found=False,
                )
            ]

    class FakeDetector:
        def detect_source(self, video, settings, work_dir):
            copied = Path(work_dir) / "source.srt"
            shutil.copy2(source_srt, copied)
            return SubtitleSourceResult(
                video_path=video.path,
                source_type="sidecar_srt",
                source_srt_path=str(copied),
                language="zh",
            )

    class FakeTranslator:
        def translate_srt(self, source_srt_path, output_srt_path, **kwargs):
            Path(output_srt_path).write_text("1\n00:00:00,000 --> 00:00:01,000\nXin chao\n", encoding="utf-8")
            return TranslationResult(
                source_srt_path=source_srt_path,
                translated_srt_path=output_srt_path,
                provider="fake",
            )

    class RenderMustNotRun:
        def render_video_with_translated_subtitle(self, *args, **kwargs):
            raise AssertionError("render pipeline should not run before subtitle review")

    summary = DouyinReupService(
        scanner=FakeScanner(),
        source_detector=FakeDetector(),
        translator=FakeTranslator(),
        render_pipeline=RenderMustNotRun(),
    ).process_folder(_project_config(source_dir, output_dir), project_id="project-review", job_id="job-review")

    assert summary["successful_outputs"] == 1
    assert summary["failed_outputs"] == 0
    assert summary["outputs"][0]["status"] == "needs_review"
    assert summary["outputs"][0]["subtitle_review_document_id"]
    assert summary["subtitle_review"]["documents_created"] == 1
    assert summary["failed_items"] == []

    documents = SubtitleReviewService().list_documents(job_id="job-review")
    assert len(documents) == 1
    assert documents[0].lines[0].translated_text == "Xin chao"
