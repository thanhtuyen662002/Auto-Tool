from __future__ import annotations

from pathlib import Path

from app.modules.douyin_reup.douyin_schema import DouyinReupSettings
from app.modules.silent_immersive_reup.silent_reup_pipeline import SilentReupPipeline
from app.modules.silent_immersive_reup.silent_schema import SilentVisualSegment, SpeechPresenceResult, VisualSegmentType
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
                id="seg_001",
                video_path=video_path,
                start=0,
                end=2,
                duration=2,
                segment_type=VisualSegmentType.product_reveal,
                visual_score=0.8,
            )
        ]


class FakeRenderPipeline:
    def render_video_with_srt(self, video, subtitle_srt_path, settings, output_dir, output_name, warnings=None, voiceover_path=None):
        output = Path(output_dir) / output_name
        output.write_bytes(b"fake mp4")
        return {
            "path": str(output),
            "subtitle_ass_file": str(Path(output_dir) / "sub.ass"),
            "bgm_file": None,
            "warnings": warnings or [],
            "errors": [],
        }


def test_silent_pipeline_builds_plan_and_writes_srt(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")
    settings = DouyinReupSettings(enabled=True, preset_id="silent_chill_immersive", use_ocr_if_no_subtitle=False)

    pipeline = SilentReupPipeline(speech_detector=FakeDetector(), visual_analyzer=FakeAnalyzer())
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
        review_subtitles_before_render=False,
        auto_render_after_translation=True,
    )

    pipeline = SilentReupPipeline(
        speech_detector=FakeDetector(),
        visual_analyzer=FakeAnalyzer(),
        render_pipeline=FakeRenderPipeline(),
    )
    plan = pipeline.build_plan(str(video), settings, str(tmp_path / "work"), None)
    result = pipeline.render_from_plan(plan, settings, str(tmp_path / "render"))

    assert result.status == "success"
    assert result.output_video_path
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
    assert any("disabled" in warning for warning in plan.warnings)
