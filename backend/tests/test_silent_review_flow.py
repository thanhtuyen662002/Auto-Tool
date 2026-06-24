from __future__ import annotations

from pathlib import Path

from app import database
from app.api import run_subtitle_review_render_job
from app.modules.douyin_reup.douyin_reup_service import DouyinReupService
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, DouyinReupSummary, DouyinVideoItem
from app.modules.silent_immersive_reup.silent_reup_pipeline import SilentReupPipeline
from app.modules.silent_immersive_reup.silent_schema import ImmersiveCaptionLine, SilentReupPlan
from app.modules.subtitle_review import ApproveSubtitleDocumentRequest, SubtitleReviewService, UpdateSubtitleLineRequest
from app.schemas.project_schema import ProjectConfig
from tests.final_output_qa_helpers import make_video


class FakeVoiceGenerator:
    warnings: list[str] = []

    def generate_voiceover(self, _script, output_dir, filename, **_kwargs):
        path = Path(output_dir) / filename
        path.write_bytes(b"voice")
        return str(path)


class FakeReviewRenderPipeline:
    def __init__(self) -> None:
        self.voiceover_path = None

    def render_from_review_document(self, document_id, settings, output_dir, voiceover_path=None):
        self.voiceover_path = voiceover_path
        output = Path(output_dir) / "reviewed.mp4"
        output.write_bytes(b"video")
        return {
            "path": str(output),
            "duration": 2.0,
            "source_video": "source.mp4",
            "translated_srt_file": "caption.srt",
            "corrected_srt_file": "caption.corrected.srt",
            "corrected_ass_file": None,
            "subtitle_ass_file": None,
            "overlay_file": None,
            "bgm_file": None,
            "voiceover_file": voiceover_path,
            "warnings": [],
            "errors": [],
        }


class FakeScanner:
    def __init__(self, video_path: str) -> None:
        self.video_path = video_path

    def scan_folder(self, _folder):
        return [
            DouyinVideoItem(
                path=self.video_path,
                filename=Path(self.video_path).name,
                duration=2,
                width=1080,
                height=1920,
                fps=30,
                has_audio=True,
            )
        ]


class FakeSilentPlanPipeline:
    last_ocr_source_srt_path = None
    last_ocr_debug_json_path = None
    last_ocr_frame_count = 0
    last_ocr_detected_line_count = 0
    last_ocr_average_confidence = 0.0
    last_voiceover_script_path = None
    last_voiceover_subtitle_path = None

    def build_plan(self, video_path, settings, output_dir, product_context=None, **_kwargs):
        plan = SilentReupPlan(
            video_path=video_path,
            strategy=settings.silent_mode_strategy,
            has_speech=False,
            speech_score=0.1,
            visual_segments=[],
            captions=[ImmersiveCaptionLine(index=1, start=0, end=2, text="Caption tu canh")],
            recommended_audio_mode="original_audio_plus_bgm",
        )
        path = Path(output_dir) / "silent_reup_plan.json"
        path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
        self.last_plan_path = str(path)
        return plan

    def write_caption_srt(self, _plan, output_dir, filename):
        path = Path(output_dir) / filename
        path.write_text("1\n00:00:00,000 --> 00:00:02,000\nCaption tu canh\n", encoding="utf-8")
        return str(path)


def test_silent_review_context_persists_and_voiceover_uses_approved_caption(tmp_path, monkeypatch):
    database.DB_PATH = tmp_path / "silent-review.db"
    database.init_db()
    monkeypatch.setattr("app.modules.subtitle_review.subtitle_review_service._duration_ms", lambda _path: None)
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    translated = tmp_path / "caption.srt"
    translated.write_text("1\n00:00:00,000 --> 00:00:02,000\nCaption ban dau\n", encoding="utf-8")
    plan = SilentReupPlan(
        video_path=str(video),
        strategy="product_review_voiceover",
        has_speech=False,
        speech_score=0.1,
        visual_segments=[],
        captions=[ImmersiveCaptionLine(index=1, start=0, end=2, text="Caption ban dau")],
        generate_voiceover=True,
        recommended_audio_mode="voiceover_plus_original_audio",
    )
    plan_path = tmp_path / "silent_reup_plan.json"
    plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    settings = DouyinReupSettings(
        enabled=True,
        preset_id="silent_product_voiceover",
        silent_mode_strategy="product_review_voiceover",
        generate_voiceover_for_silent_video=True,
        use_ocr_if_no_subtitle=False,
    )
    service = SubtitleReviewService()
    document = service.create_document_from_srt(
        video_id="silent-1",
        video_path=str(video),
        translated_srt_path=str(translated),
        source_type="visual_generated",
        context={
            "reup_mode": "silent_immersive",
            "silent_strategy": "product_review_voiceover",
            "silent_plan_file": str(plan_path),
            "speech_score": 0.1,
            "product_context": {"product_name": "Ke bep"},
            "settings_snapshot": settings.model_dump(mode="json"),
        },
    )
    saved = service.get_document(document.id)
    assert saved.context["reup_mode"] == "silent_immersive"
    service.update_line(document.id, 1, request=UpdateSubtitleLineRequest(edited_text="Caption da duyet"))
    approved = service.approve_document(document.id, ApproveSubtitleDocumentRequest(generate_ass=False))
    renderer = FakeReviewRenderPipeline()
    pipeline = SilentReupPipeline(render_pipeline=renderer, voice_generator=FakeVoiceGenerator())

    result = pipeline.render_review_document(approved, settings, str(tmp_path / "render"))

    assert renderer.voiceover_path and Path(renderer.voiceover_path).exists()
    assert result["voiceover_file"] == renderer.voiceover_path
    assert Path(result["voiceover_script_file"]).exists()
    assert Path(result["voiceover_subtitle_file"]).exists()
    assert "Caption da duyet" in Path(result["voiceover_script_file"]).read_text(encoding="utf-8")


def test_douyin_silent_review_mode_creates_review_document_with_context(tmp_path, monkeypatch):
    database.DB_PATH = tmp_path / "silent-douyin-review.db"
    database.init_db()
    monkeypatch.setattr("app.modules.subtitle_review.subtitle_review_service._duration_ms", lambda _path: None)
    video = tmp_path / "source" / "clip.mp4"
    video.parent.mkdir()
    video.write_bytes(b"video")
    output = tmp_path / "output"
    settings = DouyinReupSettings(
        enabled=True,
        preset_id="silent_chill_immersive",
        preset_name="Silent Chill",
        silent_review_before_render=True,
        auto_render_after_translation=False,
        use_ocr_if_no_subtitle=False,
    )
    config = ProjectConfig.model_validate(
        {
            "project_name": "silent-review",
            "source_folder": str(video.parent),
            "output_folder": str(output),
            "product": {"name": "Ke bep", "brand": "", "description": "x", "features": ["gon"], "cta": "Xem them"},
            "render": {"output_count": 1, "duration": 8, "aspect_ratio": "9:16", "resolution": "1080x1920", "fps": 30},
            "effects": {"cut_intensity": 0, "speed_variation": 0, "grain": 0, "zoom_motion": 0, "overlay_height": 22, "subtitle_size": 54},
            "ai": {"text_model": "mock", "tone": "translator", "language": "vi", "gemini_api_keys": []},
            "douyin_reup": settings.model_dump(mode="json"),
        }
    )
    service = DouyinReupService(
        scanner=FakeScanner(str(video)),
        silent_pipeline=FakeSilentPlanPipeline(),
        subtitle_review_service=SubtitleReviewService(),
    )

    summary = service.process_folder(config, project_id="project-silent", job_id="job-silent")

    result = summary["outputs"][0]
    assert result["status"] == "needs_review"
    document = SubtitleReviewService().get_document(result["subtitle_review_document_id"])
    assert document.source_type == "visual_generated"
    assert document.context["reup_mode"] == "silent_immersive"
    assert document.context["product_context"]["product_name"] == "Ke bep"


def test_silent_review_render_job_returns_valid_douyin_summary(tmp_path):
    database.DB_PATH = tmp_path / "silent-review-render.db"
    database.init_db()
    video = make_video(tmp_path / "clip.mp4", duration=3.2)
    translated = tmp_path / "caption.srt"
    translated.write_text("1\n00:00:00,200 --> 00:00:02,800\nCaption da duyet\n", encoding="utf-8")
    settings = DouyinReupSettings(
        enabled=True,
        preset_id="silent_chill_immersive",
        silent_mode_strategy="chill_immersive",
        generate_voiceover_for_silent_video=False,
        keep_immersive_original_audio=True,
        add_bgm_for_silent_video=False,
        add_bgm=False,
        add_overlay=False,
        silent_review_before_render=False,
        review_subtitles_before_render=False,
        auto_render_after_translation=True,
        use_ocr_if_no_subtitle=False,
    )
    plan = SilentReupPlan(
        video_path=str(video),
        strategy="chill_immersive",
        has_speech=False,
        speech_score=0.1,
        visual_segments=[],
        captions=[ImmersiveCaptionLine(index=1, start=0.2, end=2.8, text="Caption da duyet")],
        recommended_audio_mode="original_audio",
    )
    plan_path = tmp_path / "silent_reup_plan.json"
    plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    product_detection = {"top_candidate": {"normalized_name": "Ke bep"}, "average_confidence": 0.82}
    service = SubtitleReviewService()
    document = service.create_document_from_srt(
        video_id="silent-render",
        video_path=str(video),
        translated_srt_path=str(translated),
        source_type="visual_generated",
        context={
            "reup_mode": "silent_immersive",
            "silent_strategy": "chill_immersive",
            "silent_plan_file": str(plan_path),
            "product_detection": product_detection,
            "settings_snapshot": settings.model_dump(mode="json"),
        },
    )
    approved = service.approve_document(document.id, ApproveSubtitleDocumentRequest(generate_ass=False))
    database.create_project("review-project", {"project_name": "silent-review-render"})
    database.create_job("review-job", "review-project", preview_only=False, total_outputs=1)

    run_subtitle_review_render_job(
        "review-job",
        [approved.id],
        str(tmp_path / "output"),
        settings.model_dump(mode="json"),
    )

    job = database.get_job("review-job")
    assert job["status"] == "completed"
    DouyinReupSummary.model_validate(job["results"]["summary"])
    output = job["results"]["outputs"][0]
    assert output["reup_mode"] == "silent_immersive"
    assert output["product_detection"] == product_detection
    assert output["final_output_qa"]["status"] in {"passed", "passed_with_warnings"}
