from __future__ import annotations

from pathlib import Path

from app import database
from app.modules.douyin_reup.douyin_reup_service import DouyinReupService
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, DouyinVideoItem, SubtitleSourceResult, TranslationResult
from app.schemas.project_schema import ProjectConfig


def _config(source_dir: Path, output_dir: Path) -> ProjectConfig:
    return ProjectConfig.model_validate(
        {
            "project_name": "douyin-e2e-flow",
            "source_folder": str(source_dir),
            "output_folder": str(output_dir),
            "product": {"name": "x", "brand": "", "description": "x", "features": ["x"], "cta": "x"},
            "render": {"output_count": 1, "duration": 8, "aspect_ratio": "9:16", "resolution": "1080x1920", "fps": 30},
            "effects": {"cut_intensity": 0, "speed_variation": 0, "grain": 0, "zoom_motion": 0, "overlay_height": 22, "subtitle_size": 54},
            "ai": {"text_model": "mock", "tone": "translator", "language": "vi", "gemini_api_keys": []},
            "douyin_reup": DouyinReupSettings(enabled=True).model_dump(mode="json"),
        }
    )


def test_e2e_review_mode_batch_continues_when_one_video_fails(tmp_path: Path, monkeypatch):
    database.DB_PATH = tmp_path / "e2e.db"
    monkeypatch.setattr("app.modules.subtitle_review.subtitle_review_service._duration_ms", lambda _path: None)
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "out"
    source_dir.mkdir()
    good_video = source_dir / "good.mp4"
    bad_video = source_dir / "bad.mp4"
    source_srt = source_dir / "good.srt"
    good_video.write_bytes(b"fake")
    bad_video.write_bytes(b"fake")
    source_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nNi hao\n", encoding="utf-8")

    class FakeScanner:
        def scan_folder(self, _folder):
            return [
                DouyinVideoItem(path=str(good_video), filename=good_video.name, duration=8, width=1080, height=1920, fps=30, has_audio=True, sidecar_srt_path=str(source_srt), embedded_subtitle_found=False),
                DouyinVideoItem(path=str(bad_video), filename=bad_video.name, duration=8, width=1080, height=1920, fps=30, has_audio=False, embedded_subtitle_found=False),
            ]

    class FakeDetector:
        def detect_source(self, video, settings, work_dir):
            if Path(video.path).name == "bad.mp4":
                return SubtitleSourceResult(video_path=video.path, source_type="none", errors=["ASR thất bại: audio quá nhỏ"])
            target = Path(work_dir) / "source.srt"
            target.write_text(source_srt.read_text(encoding="utf-8"), encoding="utf-8")
            return SubtitleSourceResult(video_path=video.path, source_type="sidecar_srt", source_srt_path=str(target))

    class FakeTranslator:
        def translate_srt(self, source_srt_path, output_srt_path, **_kwargs):
            Path(output_srt_path).write_text("1\n00:00:00,000 --> 00:00:01,000\nXin chao\n", encoding="utf-8")
            return TranslationResult(source_srt_path=source_srt_path, translated_srt_path=output_srt_path, provider="mock")

    summary = DouyinReupService(
        scanner=FakeScanner(),
        source_detector=FakeDetector(),
        translator=FakeTranslator(),
    ).process_folder(_config(source_dir, output_dir), project_id="project-e2e", job_id="job-e2e")

    assert summary["needs_review"] == 1
    assert summary["failed_outputs"] == 1
    assert summary["failure_breakdown"] == {"asr_failed": 1}
    failed = next(output for output in summary["outputs"] if output["status"] == "failed")
    assert failed["failed_step"] == "asr"
    assert failed["can_retry"] is True
