from __future__ import annotations

from pathlib import Path

from app.modules.douyin_reup.douyin_schema import DouyinReupSettings
from app.modules.silent_immersive_reup.silent_reup_pipeline import SilentReupPipeline
from app.modules.silent_immersive_reup.silent_schema import (
    SilentProductDetectionReport,
    SilentVisualSegment,
    SpeechPresenceResult,
    VisualSegmentType,
)
from app.schemas.media_schema import MediaFile


class FakeDetector:
    def detect(self, video_path: str):
        return SpeechPresenceResult(
            video_path=video_path,
            has_speech=False,
            speech_score=0.1,
            audio_energy_score=0.2,
            speech_segments_count=0,
            method="fake",
        )


class FakeAnalyzer:
    def analyze_video(self, video_path, settings, output_dir):
        return [
            SilentVisualSegment(
                id=f"seg_{index:03d}",
                video_path=video_path,
                start=(index - 1) * 2,
                end=index * 2,
                duration=2,
                segment_type=VisualSegmentType.product_reveal,
                visual_score=0.8,
            )
            for index in range(1, 4)
        ]


class FakeProductDetector:
    def detect(self, video_path, segments, visual_tag_report, product_context=None, gemini_api_keys=None):
        return SilentProductDetectionReport(
            video_path=video_path,
            provider="heuristic_fallback",
            status="detected",
            candidates=[],
            average_confidence=0.9,
            warnings=[],
            created_at="2026-06-25T00:00:00",
        )


class FakeRenderPipeline:
    def render_video_with_srt(self, video, subtitle_srt_path, settings, output_dir, output_name, warnings=None, voiceover_path=None):
        output = Path(output_dir) / output_name
        output.write_bytes(b"fake mp4")
        return {
            "path": str(output),
            "subtitle_ass_file": str(Path(output_dir) / "sub.ass") if settings.burn_subtitle else None,
            "bgm_file": None,
            "warnings": warnings or [],
            "errors": [],
        }


def test_silent_pipeline_builds_plan_and_writes_srt(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")
    settings = DouyinReupSettings(
        enabled=True,
        preset_id="silent_chill_immersive",
        use_ocr_if_no_subtitle=False,
        generate_visual_captions=True,
    )

    pipeline = SilentReupPipeline(
        speech_detector=FakeDetector(),
        visual_analyzer=FakeAnalyzer(),
        product_detector=FakeProductDetector(),
    )
    plan = pipeline.build_plan(str(video), settings, str(tmp_path / "work"), {"product_name": "Kệ bếp"})
    srt_path = pipeline.write_caption_srt(plan, str(tmp_path / "work"), "caption.srt")

    assert plan.has_speech is False
    assert plan.captions
    assert plan.product_detection is not None
    assert Path(srt_path).exists()
    assert Path(pipeline.last_plan_path or "").exists()


def test_silent_pipeline_render_from_plan_uses_existing_renderer(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.modules.silent_immersive_reup.silent_reup_pipeline.probe_video",
        lambda path: MediaFile(
            path=path,
            duration=2,
            width=1080,
            height=1920,
            fps=30,
            has_audio=True,
            format_name="mov,mp4",
        ),
    )
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")
    settings = DouyinReupSettings(
        enabled=True,
        preset_id="silent_chill_immersive",
        use_ocr_if_no_subtitle=False,
        generate_visual_captions=True,
        review_subtitles_before_render=False,
        auto_render_after_translation=True,
    )

    pipeline = SilentReupPipeline(
        speech_detector=FakeDetector(),
        visual_analyzer=FakeAnalyzer(),
        render_pipeline=FakeRenderPipeline(),
        product_detector=FakeProductDetector(),
    )
    plan = pipeline.build_plan(str(video), settings, str(tmp_path / "work"), None)
    result = pipeline.render_from_plan(plan, settings, str(tmp_path / "render"))

    assert result.status == "success"
    assert result.output_video_path
    assert result.output_video_path.endswith(".mp4")
    assert Path(result.output_video_path).exists()
    assert Path(result.caption_srt_path or "").exists()


def test_silent_pipeline_respects_disabled_visual_caption_generation(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")
    settings = DouyinReupSettings(
        enabled=True,
        preset_id="silent_chill_immersive",
        use_ocr_if_no_subtitle=False,
        generate_visual_captions=False,
    )

    pipeline = SilentReupPipeline(speech_detector=FakeDetector(), visual_analyzer=FakeAnalyzer())
    plan = pipeline.build_plan(str(video), settings, str(tmp_path / "work"), None)

    assert plan.captions == []
    assert any("No reliable OCR" in warning or "silent_safe_music_only" in warning for warning in plan.warnings)


def test_silent_caption_does_not_prefix_product_name_with_colon(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")
    settings = DouyinReupSettings(
        enabled=True,
        preset_id="silent_chill_immersive",
        use_ocr_if_no_subtitle=False,
        generate_visual_captions=True,
    )

    pipeline = SilentReupPipeline(
        speech_detector=FakeDetector(),
        visual_analyzer=FakeAnalyzer(),
        product_detector=FakeProductDetector(),
    )
    plan = pipeline.build_plan(str(video), settings, str(tmp_path / "work"), {"product_name": "Ke bep"})

    assert plan.captions
    assert all(not caption.text.startswith("Ke bep:") for caption in plan.captions)


def test_silent_pipeline_falls_back_to_music_only_when_voiceover_would_be_unsafe(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.modules.silent_immersive_reup.silent_reup_pipeline.probe_video",
        lambda path: MediaFile(
            path=path,
            duration=2,
            width=1080,
            height=1920,
            fps=30,
            has_audio=True,
            format_name="mov,mp4",
        ),
    )
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")
    bgm = tmp_path / "song.mp3"
    bgm.write_bytes(b"fake audio")
    settings = DouyinReupSettings(
        enabled=True,
        preset_id="silent_product_voiceover",
        use_ocr_if_no_subtitle=False,
        review_subtitles_before_render=False,
        auto_render_after_translation=True,
        generate_voiceover_for_silent_video=True,
        keep_immersive_original_audio=True,
        add_bgm_for_silent_video=True,
        favorite_music_paths=[str(bgm)],
    )
    captured = {}

    class CaptureRenderPipeline(FakeRenderPipeline):
        def render_video_with_srt(self, video, subtitle_srt_path, settings, output_dir, output_name, warnings=None, voiceover_path=None):
            captured["settings"] = settings
            captured["output_name"] = output_name
            captured["voiceover_path"] = voiceover_path
            return super().render_video_with_srt(video, subtitle_srt_path, settings, output_dir, output_name, warnings, voiceover_path)

    pipeline = SilentReupPipeline(
        speech_detector=FakeDetector(),
        visual_analyzer=FakeAnalyzer(),
        render_pipeline=CaptureRenderPipeline(),
    )
    work_dir = tmp_path / "video_001"
    plan = pipeline.build_plan(str(video), settings, str(work_dir), None)
    result = pipeline.render_from_plan(plan, settings, str(work_dir))

    assert plan.captions == []
    assert plan.generate_voiceover is False
    assert plan.recommended_audio_mode == "music_only_safe"
    assert any("silent_safe_music_only" in warning for warning in plan.warnings)
    assert result.status == "success"
    assert result.caption_srt_path is None
    assert captured["output_name"] == "video_001_silent.mp4"
    assert captured["voiceover_path"] is None
    assert captured["settings"].burn_subtitle is False
    assert captured["settings"].generate_voiceover_for_silent_video is False
    assert captured["settings"].keep_original_audio is False
