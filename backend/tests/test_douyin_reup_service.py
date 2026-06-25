from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from app.modules.douyin_reup.douyin_reup_service import DouyinReupService, _douyin_run_folder_name, _product_context
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, DouyinVideoItem, SubtitleSourceResult, TranslationResult
from app.modules.job_recovery import JobCheckpointService, JobStepStatus, RecoverableStep
from app.modules.silent_immersive_reup.silent_schema import (
    ImmersiveCaptionLine,
    SilentReupPlan,
    SilentReupResult,
    SpeechPresenceResult,
)
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


def test_douyin_run_folder_name_does_not_repeat_default_project_slug():
    created_at = datetime(2026, 6, 20, 23, 12, 22)

    assert _douyin_run_folder_name("douyin_reup_2026_06_20", created_at) == "douyin_reup_2026_06_20-231222"
    assert _douyin_run_folder_name("my-shop", created_at) == "my-shop-2026-06-20-231222"


def test_default_silent_product_context_uses_auto_detection(tmp_path):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir()
    output_dir.mkdir()
    payload = _project_config(tmp_path, source_dir, output_dir).model_dump(mode="json")
    payload.update(
        {
            "product": {
                "name": "Douyin Reup",
                "brand": "",
                "description": "Xử lý video Douyin local với subtitle/caption tiếng Việt.",
                "features": ["Dịch subtitle", "Thêm overlay", "Trộn nhạc nền"],
                "cta": "Xem video",
            },
            "douyin_reup": DouyinReupSettings(
                enabled=True,
                preset_id="silent_chill_immersive",
                product_context_lock_enabled=True,
            ).model_dump(mode="json"),
        }
    )

    context = _product_context(ProjectConfig.model_validate(payload))

    assert context["product_context_lock_enabled"] is False
    assert context["auto_detect_product_context"] is True
    assert context["product_name"] == ""
    assert context["features"] == []


def test_douyin_reup_service_processes_each_video_without_crashing_batch(tmp_path, monkeypatch):
    monkeypatch.setattr("app.modules.job_recovery.job_checkpoint_service.app_data_dir", lambda: tmp_path / "appdata")
    monkeypatch.setattr("app.modules.queue_control.queue_state_service.app_data_dir", lambda: tmp_path / "appdata")
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
    ).process_folder(config, project_id="project-1", job_id="job-1")

    assert summary["successful_outputs"] == 1
    assert summary["failed_outputs"] == 0
    assert summary["outputs"][0]["status"] == "success"
    assert Path(summary["summary_file"]).exists()
    checkpoints = JobCheckpointService(storage_root=tmp_path / "appdata" / "data" / "job_recovery").load_video_checkpoints("job-1")
    assert any(
        item.video_id == "video_001"
        and item.step == RecoverableStep.render
        and item.status == JobStepStatus.completed
        for item in checkpoints
    )


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


def test_silent_batch_does_not_auto_route_audio_energy_only_to_voice_flow(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir()
    output_dir.mkdir()
    video_path = source_dir / "ambient.mp4"
    video_path.write_bytes(b"fake video")

    monkeypatch.setattr(
        "app.modules.douyin_reup.douyin_reup_service.speech_result_for_video",
        lambda video_path, settings: SpeechPresenceResult(
            video_path=video_path,
            has_speech=True,
            speech_score=0.34,
            audio_energy_score=1.0,
            speech_segments_count=0,
            method="audio_energy_heuristic",
            warnings=["Chỉ dùng audio energy heuristic."],
        ),
    )

    settings = DouyinReupSettings(
        enabled=True,
        preset_id="silent_chill_immersive",
        silent_mode_detection=True,
        detect_speech_presence=True,
        auto_route_speech_to_voice_reup=True,
        auto_route_speech_threshold=0.28,
    )
    video = DouyinVideoItem(
        path=str(video_path),
        filename=video_path.name,
        duration=8,
        width=1080,
        height=1920,
        fps=30,
        has_audio=True,
    )
    service = DouyinReupService()

    routed = service._route_silent_video_to_voice_if_needed(
        index=1,
        video=video,
        config=_project_config(tmp_path, source_dir, output_dir).model_copy(update={"douyin_reup": settings}),
        settings=settings,
        output_root=output_dir,
        project_id=None,
        job_id=None,
        step_progress_callback=None,
    )

    assert routed is None


def test_silent_batch_does_not_auto_route_single_weak_asr_segment(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir()
    output_dir.mkdir()
    video_path = source_dir / "credit_only.mp4"
    video_path.write_bytes(b"fake video")

    monkeypatch.setattr(
        "app.modules.douyin_reup.douyin_reup_service.speech_result_for_video",
        lambda video_path, settings: SpeechPresenceResult(
            video_path=video_path,
            has_speech=True,
            speech_score=0.4,
            audio_energy_score=0.9,
            speech_segments_count=1,
            method="asr_fast_detect",
            warnings=[],
        ),
    )

    settings = DouyinReupSettings(
        enabled=True,
        preset_id="silent_chill_immersive",
        silent_mode_detection=True,
        detect_speech_presence=True,
        auto_route_speech_to_voice_reup=True,
        auto_route_speech_threshold=0.28,
    )
    video = DouyinVideoItem(
        path=str(video_path),
        filename=video_path.name,
        duration=8,
        width=1080,
        height=1920,
        fps=30,
        has_audio=True,
    )

    routed = DouyinReupService()._route_silent_video_to_voice_if_needed(
        index=1,
        video=video,
        config=_project_config(tmp_path, source_dir, output_dir).model_copy(update={"douyin_reup": settings}),
        settings=settings,
        output_root=output_dir,
        project_id=None,
        job_id=None,
        step_progress_callback=None,
    )

    assert routed is None


def test_silent_batch_does_not_auto_route_ambiguous_speech_score_to_voice_flow(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir()
    output_dir.mkdir()
    video_path = source_dir / "maybe-speech.mp4"
    video_path.write_bytes(b"fake video")

    monkeypatch.setattr(
        "app.modules.douyin_reup.douyin_reup_service.speech_result_for_video",
        lambda video_path, settings: SpeechPresenceResult(
            video_path=video_path,
            has_speech=True,
            speech_score=0.5,
            audio_energy_score=0.8,
            speech_segments_count=3,
            method="asr_fast_detect",
            warnings=[],
        ),
    )

    settings = DouyinReupSettings(
        enabled=True,
        preset_id="silent_chill_immersive",
        silent_mode_detection=True,
        detect_speech_presence=True,
        auto_route_speech_to_voice_reup=True,
        auto_route_speech_threshold=0.28,
    )
    video = DouyinVideoItem(
        path=str(video_path),
        filename=video_path.name,
        duration=8,
        width=1080,
        height=1920,
        fps=30,
        has_audio=True,
    )

    routed = DouyinReupService()._route_silent_video_to_voice_if_needed(
        index=1,
        video=video,
        config=_project_config(tmp_path, source_dir, output_dir).model_copy(update={"douyin_reup": settings}),
        settings=settings,
        output_root=output_dir,
        project_id=None,
        job_id=None,
        step_progress_callback=None,
    )

    assert routed is None


def test_voice_batch_auto_routes_no_speech_video_to_silent_flow(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir()
    output_dir.mkdir()
    video_path = source_dir / "silent.mp4"
    video_path.write_bytes(b"fake video")

    monkeypatch.setattr(
        "app.modules.douyin_reup.douyin_reup_service.speech_result_for_video",
        lambda video_path, settings: SpeechPresenceResult(
            video_path=video_path,
            has_speech=False,
            speech_score=0.05,
            audio_energy_score=0.1,
            speech_segments_count=0,
            method="test",
            warnings=[],
        ),
    )

    class FakeDetector:
        def detect_source(self, video, settings, work_dir):
            return SubtitleSourceResult(
                video_path=video.path,
                source_type="none",
                source_srt_path=None,
                language="zh",
                errors=["Không có phụ đề hoặc lời thoại đủ rõ."],
            )

    class FakeSilentPipeline:
        last_plan_path = None
        last_ocr_source_srt_path = None
        last_voiceover_script_path = None
        last_voiceover_subtitle_path = None
        last_ocr_debug_json_path = None
        last_ocr_frame_count = 0
        last_ocr_detected_line_count = 0
        last_ocr_average_confidence = 0.0

        def build_plan(self, video_path, settings, output_dir, product_context=None, gemini_api_keys=None):
            assert settings.preset_id == "silent_chill_immersive"
            assert settings.auto_route_speech_to_voice_reup is False
            plan_path = Path(output_dir) / "silent_reup_plan.json"
            plan_path.write_text("{}", encoding="utf-8")
            self.last_plan_path = str(plan_path)
            return SilentReupPlan(
                video_path=video_path,
                strategy=settings.silent_mode_strategy,
                has_speech=False,
                speech_score=0.05,
                visual_segments=[],
                captions=[
                    ImmersiveCaptionLine(
                        index=1,
                        start=0,
                        end=2,
                        text="Caption theo cảnh",
                    )
                ],
                recommended_audio_mode="original_audio_plus_bgm",
            )

        def write_caption_srt(self, plan, output_dir, filename):
            path = Path(output_dir) / filename
            path.write_text("1\n00:00:00,000 --> 00:00:02,000\nCaption theo cảnh\n", encoding="utf-8")
            return str(path)

        def render_from_plan(self, plan, settings, output_dir, **kwargs):
            output = Path(output_dir) / "silent_reup.mp4"
            output.write_bytes(b"fake mp4")
            return SilentReupResult(
                input_video_path=plan.video_path,
                output_video_path=str(output),
                plan_path=self.last_plan_path,
                caption_srt_path=str(Path(output_dir) / "video_001_silent_vi.srt"),
                status="success",
            )

    config = _project_config(tmp_path, source_dir, output_dir)
    settings = DouyinReupSettings(
        enabled=True,
        preset_id="voice_priority",
        preset_name="Có thoại",
        review_subtitles_before_render=False,
        auto_render_after_translation=True,
        auto_route_no_speech_to_silent_reup=True,
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
    )

    result = DouyinReupService(
        source_detector=FakeDetector(),
        silent_pipeline=FakeSilentPipeline(),
    )._process_one_video(1, video, config, settings, output_dir)

    assert result.status == "success"
    assert result.reup_mode == "auto_routed_silent_immersive"
    assert result.speech_score == 0.05


def test_voice_batch_routes_asr_failed_no_speech_to_silent_flow(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir()
    output_dir.mkdir()
    video_path = source_dir / "silent-asr-failed.mp4"
    video_path.write_bytes(b"fake video")

    monkeypatch.setattr(
        "app.modules.douyin_reup.douyin_reup_service.speech_result_for_video",
        lambda video_path, settings: SpeechPresenceResult(
            video_path=video_path,
            has_speech=False,
            speech_score=0.04,
            audio_energy_score=0.08,
            speech_segments_count=0,
            method="test",
            warnings=[],
        ),
    )

    class FakeDetector:
        def detect_source(self, video, settings, work_dir):
            return SubtitleSourceResult(
                video_path=video.path,
                source_type="none",
                source_srt_path=None,
                language="zh",
                errors=["ASR thất bại: không nhận diện được phụ đề từ audio của video."],
            )

    class FakeSilentPipeline:
        last_plan_path = None
        last_ocr_source_srt_path = None
        last_voiceover_script_path = None
        last_voiceover_subtitle_path = None
        last_ocr_debug_json_path = None
        last_ocr_frame_count = 0
        last_ocr_detected_line_count = 0
        last_ocr_average_confidence = 0.0

        def build_plan(self, video_path, settings, output_dir, product_context=None, gemini_api_keys=None):
            plan_path = Path(output_dir) / "silent_reup_plan.json"
            plan_path.write_text("{}", encoding="utf-8")
            self.last_plan_path = str(plan_path)
            return SilentReupPlan(
                video_path=video_path,
                strategy=settings.silent_mode_strategy,
                has_speech=False,
                speech_score=0.04,
                visual_segments=[],
                captions=[ImmersiveCaptionLine(index=1, start=0, end=2, text="Caption theo cảnh")],
                recommended_audio_mode="original_audio_plus_bgm",
            )

        def write_caption_srt(self, plan, output_dir, filename):
            path = Path(output_dir) / filename
            path.write_text("1\n00:00:00,000 --> 00:00:02,000\nCaption theo cảnh\n", encoding="utf-8")
            return str(path)

        def render_from_plan(self, plan, settings, output_dir, **kwargs):
            output = Path(output_dir) / "silent_reup.mp4"
            output.write_bytes(b"fake mp4")
            return SilentReupResult(
                input_video_path=plan.video_path,
                output_video_path=str(output),
                plan_path=self.last_plan_path,
                caption_srt_path=str(Path(output_dir) / "video_001_silent_vi.srt"),
                status="success",
            )

    class FakeFinalQAService:
        def run_qa_for_output(self, *args, **kwargs):
            return type("Report", (), {"status": "passed", "score": 100, "report_path": None, "issues": []})()

    monkeypatch.setattr("app.modules.douyin_reup.douyin_reup_service.FinalOutputQAService", FakeFinalQAService)

    config = _project_config(tmp_path, source_dir, output_dir)
    settings = DouyinReupSettings(
        enabled=True,
        preset_id="voice_priority",
        preset_name="Có thoại",
        review_subtitles_before_render=False,
        auto_render_after_translation=True,
        auto_route_no_speech_to_silent_reup=True,
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
    )

    result = DouyinReupService(
        source_detector=FakeDetector(),
        silent_pipeline=FakeSilentPipeline(),
    )._process_one_video(1, video, config, settings, output_dir)

    assert result.status == "success"
    assert result.reup_mode == "auto_routed_silent_immersive"
    assert result.speech_score == 0.04
    assert any("Tự động chuyển" in warning for warning in result.warnings)
