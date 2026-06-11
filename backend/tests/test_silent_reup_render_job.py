from __future__ import annotations

from app import database
from app.api import run_silent_reup_plan_job
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, DouyinReupSummary
from app.modules.final_output_qa.export_pack_service import ExportPackService
from app.modules.final_output_qa.final_output_qa_schema import PlatformTarget
from app.modules.silent_immersive_reup.silent_schema import ImmersiveCaptionLine, SilentReupPlan
from tests.final_output_qa_helpers import make_video


def test_standalone_silent_render_job_runs_final_qa(tmp_path):
    database.DB_PATH = tmp_path / "silent-render.db"
    database.init_db()
    video = make_video(tmp_path / "source.mp4", duration=3.2)
    project_id = "silent-project"
    job_id = "silent-job"
    database.create_project(project_id, {"project_name": "silent-render"})
    database.create_job(job_id, project_id, preview_only=False, total_outputs=1)
    plan = SilentReupPlan(
        video_path=str(video),
        strategy="chill_immersive",
        has_speech=False,
        speech_score=0.1,
        visual_segments=[],
        captions=[ImmersiveCaptionLine(index=1, start=0.2, end=2.8, text="Caption kiem tra")],
        recommended_audio_mode="original_audio",
    )
    settings = DouyinReupSettings(
        enabled=True,
        preset_id="silent_chill_immersive",
        use_ocr_if_no_subtitle=False,
        review_subtitles_before_render=False,
        silent_review_before_render=False,
        auto_render_after_translation=True,
        add_overlay=False,
        add_bgm_for_silent_video=False,
        add_bgm=False,
        keep_immersive_original_audio=True,
        keep_original_audio=True,
    )

    run_silent_reup_plan_job(job_id, plan.model_dump(mode="json"), settings.model_dump(mode="json"), str(tmp_path / "output"))

    job = database.get_job(job_id)
    output = job["results"]["outputs"][0]
    assert job["status"] == "completed"
    assert output["final_output_qa"]["status"] in {"passed", "passed_with_warnings"}
    assert output["log_file"]
    assert job["results"]["summary"]["final_output_qa"]["total_checked"] == 1
    DouyinReupSummary.model_validate(job["results"]["summary"])
    pack = ExportPackService().create_export_pack_for_job(job_id, PlatformTarget.tiktok)
    assert pack.items
