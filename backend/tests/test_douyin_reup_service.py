from __future__ import annotations

import shutil
from pathlib import Path

from app.modules.douyin_reup.douyin_reup_service import DouyinReupService
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, DouyinVideoItem, SubtitleSourceResult, TranslationResult
from app.modules.silent_immersive_reup.silent_schema import SpeechPresenceResult
from app.schemas.project_schema import ProjectConfig


def _project_config(tmp_path: Path, source_folder: Path, output_folder: Path) -> ProjectConfig:
    return ProjectConfig.model_validate(
        {
            "project_name": "douyin-test",
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
            "douyin_reup": DouyinReupSettings(
                enabled=True,
                review_subtitles_before_render=False,
                auto_render_after_translation=True,
            ).model_dump(mode="json"),
        }
    )


def test_douyin_reup_service_processes_each_video_without_crashing_batch(tmp_path):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir()
    video_path = source_dir / "clip.mp4"
    source_srt = source_dir / "clip.srt"
    video_path.write_bytes(b"fake video")
    source_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\n你好\n", encoding="utf-8")

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
            Path(output_srt_path).write_text("1\n00:00:00,000 --> 00:00:01,000\nXin chào\n", encoding="utf-8")
            return TranslationResult(
                source_srt_path=source_srt_path,
                translated_srt_path=output_srt_path,
                provider="fake",
            )

    class FakePipeline:
        def render_video_with_translated_subtitle(self, video, translation_result, settings, output_dir, output_name):
            output = Path(output_dir) / output_name
            output.write_bytes(b"fake mp4")
            return {
                "path": str(output),
                "duration": 8,
                "subtitle_ass_file": None,
                "overlay_file": None,
                "bgm_file": None,
                "warnings": [],
                "errors": [],
            }

    config = _project_config(tmp_path, source_dir, output_dir)
    summary = DouyinReupService(
        scanner=FakeScanner(),
        source_detector=FakeDetector(),
        translator=FakeTranslator(),
        render_pipeline=FakePipeline(),
    ).process_folder(config)

    assert summary["successful_outputs"] == 1
    assert summary["failed_outputs"] == 0
    assert summary["outputs"][0]["status"] == "success"
    assert Path(summary["summary_file"]).exists()


def test_silent_batch_auto_routes_speech_video_to_voice_flow(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir()
    output_dir.mkdir()
    video_path = source_dir / "clip.mp4"
    source_srt = source_dir / "clip.srt"
    video_path.write_bytes(b"fake video")
    source_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\n你好\n", encoding="utf-8")

    monkeypatch.setattr(
        "app.modules.douyin_reup.douyin_reup_service.speech_result_for_video",
        lambda video_path, settings: SpeechPresenceResult(
            video_path=video_path,
            has_speech=True,
            speech_score=0.72,
            audio_energy_score=0.8,
            speech_segments_count=2,
            method="test",
            warnings=[],
        ),
    )

    class FakeDetector:
        def detect_source(self, video, settings, work_dir):
            assert settings.enable_silent_immersive_mode is False
            assert settings.preset_id == "voice_priority"
            copied = Path(work_dir) / "source.srt"
            shutil.copy2(source_srt, copied)
            return SubtitleSourceResult(
                video_path=video.path,
                source_type="asr",
                source_srt_path=str(copied),
                language="zh",
            )

    class FakeTranslator:
        def translate_srt(self, source_srt_path, output_srt_path, **kwargs):
            Path(output_srt_path).write_text("1\n00:00:00,000 --> 00:00:01,000\nXin chào\n", encoding="utf-8")
            return TranslationResult(
                source_srt_path=source_srt_path,
                translated_srt_path=output_srt_path,
                provider="fake",
            )

    class FakePipeline:
        def render_video_with_translated_subtitle(self, video, translation_result, settings, output_dir, output_name):
            assert settings.keep_original_audio is False
            output = Path(output_dir) / output_name
            output.write_bytes(b"fake mp4")
            return {
                "path": str(output),
                "duration": 8,
                "subtitle_ass_file": None,
                "overlay_file": None,
                "bgm_file": None,
                "voiceover_file": str(Path(output_dir) / "voice.mp3"),
                "warnings": [],
                "errors": [],
            }

    config = _project_config(tmp_path, source_dir, output_dir)
    settings = DouyinReupSettings(
        enabled=True,
        preset_id="silent_chill_immersive",
        preset_name="Không thoại - Chill immersive",
        review_subtitles_before_render=False,
        silent_review_before_render=False,
        auto_render_after_translation=True,
        generate_voiceover_for_silent_video=True,
        keep_immersive_original_audio=True,
        auto_route_speech_to_voice_reup=True,
    )
    config = config.model_copy(update={"douyin_reup": settings})
    video = DouyinVideoItem(
        path=str(video_path),
        filename=video_path.name,
        duration=8,
        width=1080,
        height=1920,
        fps=30,
        has_audio=True,
        sidecar_srt_path=str(source_srt),
    )

    result = DouyinReupService(
        source_detector=FakeDetector(),
        translator=FakeTranslator(),
        render_pipeline=FakePipeline(),
    )._process_one_video(1, video, config, settings, output_dir)

    assert result.status == "success"
    assert result.reup_mode == "auto_routed_voice_reup"
    assert result.speech_score == 0.72
    assert any("Tự động chuyển" in warning for warning in result.warnings)
