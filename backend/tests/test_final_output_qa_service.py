import json
import shutil
from pathlib import Path

from app.modules.douyin_reup.douyin_reup_service import DouyinReupService
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, DouyinVideoItem, SubtitleSourceResult, TranslationResult
from app.modules.final_output_qa.final_output_qa_schema import PlatformTarget
from app.modules.final_output_qa.final_output_qa_service import FinalOutputQAService
from app.schemas.project_schema import ProjectConfig
from tests.final_output_qa_helpers import make_video


def test_missing_video_is_failed_with_critical_issue(tmp_path):
    report = FinalOutputQAService().run_qa_for_output(
        str(tmp_path / "missing.mp4"), PlatformTarget.tiktok, subtitle_expected=False
    )

    assert report.status == "failed"
    assert report.issues[0].issue_type == "missing_video_file"
    assert Path(report.report_path).exists()


def test_valid_vertical_video_passes_and_wrong_resolution_warns(tmp_path):
    valid = make_video(tmp_path / "valid.mp4")
    low = make_video(tmp_path / "low.mp4", width=540, height=960)

    valid_report = FinalOutputQAService().run_qa_for_output(str(valid), PlatformTarget.tiktok, subtitle_expected=False)
    low_report = FinalOutputQAService().run_qa_for_output(str(low), PlatformTarget.tiktok, subtitle_expected=False)

    assert valid_report.status == "passed"
    assert low_report.status == "passed_with_warnings"
    assert any(issue.issue_type == "low_resolution" for issue in low_report.issues)


def test_required_audio_missing_is_critical_but_optional_audio_passes(tmp_path):
    video = make_video(tmp_path / "silent.mp4", with_audio=False)

    required = FinalOutputQAService().run_qa_for_output(
        str(video), PlatformTarget.tiktok, subtitle_expected=False, audio_expected=True
    )
    optional = FinalOutputQAService().run_qa_for_output(
        str(video), PlatformTarget.tiktok, subtitle_expected=False, audio_expected=False
    )

    assert required.status == "failed"
    assert any(issue.issue_type == "audio_missing" and issue.severity.value == "critical" for issue in required.issues)
    assert optional.status == "passed"


def test_required_subtitle_missing_is_critical(tmp_path):
    video = make_video(tmp_path / "with_audio.mp4")

    report = FinalOutputQAService().run_qa_for_output(
        str(video),
        PlatformTarget.tiktok,
        subtitle_expected=True,
        audio_expected=True,
    )

    assert report.status == "failed"
    assert any(issue.issue_type == "subtitle_missing" and issue.severity.value == "critical" for issue in report.issues)


def test_non_preferred_video_codec_warns(tmp_path):
    video = make_video(tmp_path / "mpeg4.mp4", video_codec="mpeg4")

    report = FinalOutputQAService().run_qa_for_output(
        str(video), PlatformTarget.tiktok, subtitle_expected=False
    )

    assert report.status == "passed_with_warnings"
    assert any(issue.issue_type == "non_preferred_video_codec" for issue in report.issues)


def test_douyin_service_runs_final_qa_after_render(tmp_path):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir()
    video_path = make_video(source_dir / "clip.mp4")
    source_srt = source_dir / "clip.srt"
    source_srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nSource\n", encoding="utf-8")

    class Scanner:
        def scan_folder(self, _folder):
            return [DouyinVideoItem(path=str(video_path), filename=video_path.name, duration=3, width=1080, height=1920, fps=24, has_audio=True, sidecar_srt_path=str(source_srt))]

    class Detector:
        def detect_source(self, video, settings, work_dir):
            copied = Path(work_dir) / "source.srt"
            shutil.copy2(source_srt, copied)
            return SubtitleSourceResult(video_path=video.path, source_type="sidecar_srt", source_srt_path=str(copied))

    class Translator:
        def translate_srt(self, source_srt_path, output_srt_path, **_kwargs):
            Path(output_srt_path).write_text("1\n00:00:00,000 --> 00:00:02,000\nBan dich\n", encoding="utf-8")
            return TranslationResult(source_srt_path=source_srt_path, translated_srt_path=output_srt_path)

    class Pipeline:
        def render_video_with_translated_subtitle(self, video, translation_result, settings, output_dir, output_name):
            target = Path(output_dir) / output_name
            shutil.copy2(video.path, target)
            return {"path": str(target), "duration": 3, "subtitle_ass_file": None, "overlay_file": None, "bgm_file": None, "warnings": [], "errors": []}

    config = ProjectConfig.model_validate({
        "project_name": "qa-pipeline",
        "source_folder": str(source_dir),
        "output_folder": str(output_dir),
        "product": {"name": "x", "brand": "", "description": "x", "features": ["x"], "cta": "x"},
        "render": {"output_count": 1, "duration": 8, "aspect_ratio": "9:16", "resolution": "1080x1920", "fps": 24},
        "effects": {"cut_intensity": 0, "speed_variation": 0, "grain": 0, "zoom_motion": 0, "overlay_height": 22, "subtitle_size": 54},
        "ai": {"text_model": "mock", "tone": "translator", "language": "vi", "gemini_api_keys": []},
        "douyin_reup": DouyinReupSettings(enabled=True, review_subtitles_before_render=False, auto_render_after_translation=True, burn_subtitle=False, add_overlay=False).model_dump(mode="json"),
    })

    summary = DouyinReupService(scanner=Scanner(), source_detector=Detector(), translator=Translator(), render_pipeline=Pipeline()).process_folder(config)

    assert summary["outputs"][0]["final_output_qa"]["status"] == "passed"
    assert Path(summary["outputs"][0]["final_output_qa"]["report_path"]).exists()
    log = json.loads(Path(summary["outputs"][0]["log_file"]).read_text(encoding="utf-8"))
    assert log["final_output_qa"]["status"] == "passed"
