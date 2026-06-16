from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path

from app import database
from app.modules.final_output_qa.audio_quality_checker import AudioQualityChecker
from app.modules.final_output_qa.final_output_qa_schema import (
    FinalOutputQAIssue,
    FinalOutputQAReport,
    PlatformTarget,
    QASeverity,
)
from app.modules.final_output_qa.platform_profile_registry import get_platform_profile
from app.modules.final_output_qa.subtitle_visibility_checker import SubtitleVisibilityChecker
from app.modules.final_output_qa.video_probe_service import VideoProbeService
from app.utils.file_utils import write_json


class FinalOutputQAService:
    def __init__(
        self,
        probe_service: VideoProbeService | None = None,
        audio_checker: AudioQualityChecker | None = None,
        subtitle_checker: SubtitleVisibilityChecker | None = None,
    ) -> None:
        self.probe_service = probe_service or VideoProbeService()
        self.audio_checker = audio_checker or AudioQualityChecker()
        self.subtitle_checker = subtitle_checker or SubtitleVisibilityChecker()

    def run_qa_for_output(
        self,
        output_video_path: str,
        platform_target: PlatformTarget,
        job_id: str | None = None,
        project_id: str | None = None,
        video_id: str | None = None,
        ass_path: str | None = None,
        overlay_path: str | None = None,
        *,
        subtitle_expected: bool = True,
        audio_expected: bool = True,
        overlay_expected: bool = False,
        report_path: str | None = None,
    ) -> FinalOutputQAReport:
        profile = get_platform_profile(platform_target)
        probe = self.probe_service.probe_video(output_video_path)
        issues: list[FinalOutputQAIssue] = []

        if not probe.exists:
            issues.append(_issue("missing_video_file", "critical", "Final video file does not exist.", "Render the output again."))
        elif not probe.readable:
            issues.append(_issue("video_not_readable", "critical", "Final video cannot be read by ffprobe.", "Retry render and inspect the FFmpeg log."))
        else:
            issues.extend(_probe_issues(probe, profile, audio_expected=audio_expected))

        audio = self.audio_checker.analyze_audio(output_video_path, has_audio=probe.has_audio) if probe.exists else None
        if audio:
            if audio_expected and not audio.has_audio and not any(issue.issue_type == "audio_missing" for issue in issues):
                issues.append(_issue("audio_missing", "critical", "Final video has no audio stream although audio is required.", "Enable original audio or BGM and render again."))
            for warning in audio.warnings:
                issue_type = "audio_too_low" if "quiet" in warning.casefold() else "audio_clipping_risk" if "clip" in warning.casefold() else "audio_analysis_warning"
                suggestion = "Increase original_audio_volume or BGM volume and render again." if issue_type == "audio_too_low" else "Reduce the final mix volume and render again."
                issues.append(_issue(issue_type, "warning", warning, suggestion))

        subtitle = self.subtitle_checker.check_subtitle_visibility(
            output_video_path,
            ass_path,
            overlay_path,
            platform_target,
            subtitle_expected=subtitle_expected,
            overlay_expected=overlay_expected,
        )
        for warning in subtitle.warnings:
            issue_type = "subtitle_missing" if "subtitle file is missing" in warning.casefold() else "overlay_missing" if "overlay" in warning.casefold() else "subtitle_unsafe_zone"
            severity = "critical" if issue_type == "subtitle_missing" and subtitle_expected else "warning"
            suggestion = (
                "Render again with burn_subtitle enabled and inspect the subtitle artifact."
                if issue_type == "subtitle_missing"
                else "Review subtitle and overlay placement before posting."
            )
            issues.append(_issue(issue_type, severity, warning, suggestion))

        score = _score(issues)
        status = "failed" if any(item.severity == QASeverity.critical for item in issues) else "passed_with_warnings" if any(item.severity == QASeverity.warning for item in issues) else "passed"
        target_path = Path(report_path).expanduser().resolve() if report_path else _default_report_path(output_video_path)
        report = FinalOutputQAReport(
            id=str(uuid.uuid4()),
            job_id=job_id,
            project_id=project_id,
            video_id=video_id,
            platform_target=platform_target,
            output_video_path=str(Path(output_video_path).expanduser().resolve()),
            probe=probe,
            audio=audio,
            subtitle_visibility=subtitle,
            score=score,
            status=status,
            issues=issues,
            report_path=str(target_path),
            created_at=_now(),
        )
        write_json(target_path, report.model_dump(mode="json"))
        return report

    def run_qa_for_job(
        self,
        job_id: str,
        platform_target: PlatformTarget = PlatformTarget.tiktok,
    ) -> list[FinalOutputQAReport]:
        database.init_db()
        job = database.get_job(job_id)
        if not job:
            raise LookupError(f"Job not found: {job_id}")
        payload = job.get("results") or {}
        outputs = list(payload.get("outputs") or [])
        project = database.get_project(job.get("project_id")) if job.get("project_id") else None
        audio_expected = _project_audio_expected(project)
        reports: list[FinalOutputQAReport] = []
        for output in outputs:
            if not isinstance(output, dict) or not output.get("path"):
                continue
            report = self.run_qa_for_output(
                str(output["path"]),
                platform_target,
                job_id=job_id,
                project_id=job.get("project_id"),
                video_id=f"video_{int(output.get('index', len(reports) + 1)):03d}",
                ass_path=(
                    output.get("corrected_ass_file")
                    or output.get("subtitle_ass_file")
                    or output.get("corrected_srt_file")
                    or output.get("translated_srt_file")
                    or output.get("source_srt_file")
                ),
                overlay_path=output.get("overlay_file"),
                subtitle_expected=bool(output.get("translated_srt_file") or output.get("corrected_srt_file") or output.get("subtitle_ass_file")),
                audio_expected=audio_expected,
                overlay_expected=bool(output.get("overlay_file")),
                report_path=_report_path_for_output(output),
            )
            reports.append(report)
            output["final_output_qa"] = _report_summary(report)
            _merge_output_log(output.get("log_file"), report)

        summary = build_final_qa_summary(reports, platform_target)
        output_root = Path(job.get("output_folder") or (Path(reports[0].output_video_path).parent if reports else Path.cwd()))
        summary_path = output_root / "final_qa_summary.json"
        write_json(summary_path, summary)
        summary["summary_path"] = str(summary_path)
        existing_summary = dict(payload.get("summary") or {})
        existing_summary["final_output_qa"] = summary
        payload.update({"summary": existing_summary, "outputs": outputs, "final_output_qa_reports": [item.model_dump(mode="json") for item in reports]})
        database.update_job(job_id, results_json=json.dumps(payload, ensure_ascii=False))
        return reports


def build_final_qa_summary(reports: list[FinalOutputQAReport], platform_target: PlatformTarget) -> dict:
    breakdown = Counter(issue.issue_type for report in reports for issue in report.issues)
    return {
        "platform_target": platform_target.value,
        "total_checked": len(reports),
        "total": len(reports),
        "passed": sum(1 for report in reports if report.status == "passed"),
        "passed_with_warnings": sum(1 for report in reports if report.status == "passed_with_warnings"),
        "failed": sum(1 for report in reports if report.status == "failed"),
        "average_score": round(sum(report.score for report in reports) / len(reports), 4) if reports else 0.0,
        "issue_breakdown": dict(breakdown),
    }


def _probe_issues(probe, profile: dict, *, audio_expected: bool) -> list[FinalOutputQAIssue]:
    issues: list[FinalOutputQAIssue] = []
    if probe.duration is None or probe.duration <= 0:
        issues.append(_issue("invalid_duration", "critical", "Final video duration is invalid.", "Retry render."))
    elif probe.duration < profile["min_duration"]:
        issues.append(_issue("duration_too_short", "warning", f"Video is shorter than {profile['min_duration']} seconds.", "Confirm the clip is complete before posting."))
    elif probe.duration > profile["max_duration_warning"]:
        issues.append(_issue("duration_too_long", "warning", f"Video exceeds the suggested {profile['max_duration_warning']} second profile.", "Shorten the video or verify current platform limits."))
    if probe.width and probe.height:
        ratio = probe.width / probe.height
        if probe.height <= probe.width or abs(ratio - 9 / 16) > 0.03:
            issues.append(_issue("wrong_aspect_ratio", "warning", "Video is not close to vertical 9:16.", "Render again at 1080x1920."))
        if probe.width < 720 or probe.height < 1280:
            issues.append(_issue("low_resolution", "warning", "Resolution is below 720x1280.", "Render again at 1080x1920."))
        elif f"{probe.width}x{probe.height}" != profile["preferred_resolution"]:
            issues.append(_issue("wrong_resolution", "warning", f"Resolution differs from preferred {profile['preferred_resolution']}.", f"Render again with output resolution {profile['preferred_resolution']}."))
    if probe.fps and not any(abs(probe.fps - fps) < 0.2 for fps in profile["preferred_fps"]):
        issues.append(_issue("non_preferred_fps", "warning", f"FPS {probe.fps:g} is outside the preferred profile.", "Use 24, 25, 30 or 60 FPS."))
    if probe.video_codec and probe.video_codec.casefold() not in profile["preferred_codecs"]:
        issues.append(_issue("non_preferred_video_codec", "warning", f"Video codec {probe.video_codec} is not preferred.", "Export with H.264."))
    if probe.has_audio and probe.audio_codec and probe.audio_codec.casefold() not in profile["preferred_audio_codecs"]:
        issues.append(_issue("non_preferred_audio_codec", "warning", f"Audio codec {probe.audio_codec} is not preferred.", "Export audio as AAC."))
    if audio_expected and not probe.has_audio:
        issues.append(_issue("audio_missing", "critical", "Final video has no audio stream although audio is required.", "Enable original audio or BGM and render again."))
    if probe.file_size_mb is not None and probe.file_size_mb > profile["max_file_size_mb_warning"]:
        issues.append(_issue("file_size_too_large", "warning", "Final video file is larger than the local platform profile.", "Increase compression or reduce bitrate."))
    return issues


def _score(issues: list[FinalOutputQAIssue]) -> float:
    score = 1.0
    for issue in issues:
        score -= 0.35 if issue.severity == QASeverity.critical else 0.12 if issue.severity == QASeverity.warning else 0.03
    return round(max(0.0, score), 4)


def _issue(issue_type: str, severity: str, message: str, suggestion: str | None = None) -> FinalOutputQAIssue:
    return FinalOutputQAIssue(issue_type=issue_type, severity=QASeverity(severity), message=message, suggestion=suggestion)


def _default_report_path(output_video_path: str) -> Path:
    path = Path(output_video_path).expanduser().resolve()
    return path.with_name(f"{path.stem}_final_qa.json")


def _report_path_for_output(output: dict) -> str:
    log_path = output.get("log_file")
    index = int(output.get("index") or 1)
    if log_path:
        return str(Path(log_path).expanduser().resolve().parent / f"video_{index:03d}_final_qa.json")
    return str(_default_report_path(str(output["path"])))


def _report_summary(report: FinalOutputQAReport) -> dict:
    return {
        "status": report.status,
        "score": report.score,
        "report_path": report.report_path,
        "issues": [item.model_dump(mode="json") for item in report.issues],
    }


def _merge_output_log(log_file: str | None, report: FinalOutputQAReport) -> None:
    if not log_file:
        return
    path = Path(log_file).expanduser().resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, json.JSONDecodeError):
        payload = {}
    payload["final_output_qa"] = _report_summary(report)
    write_json(path, payload)


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _project_audio_expected(project: dict | None) -> bool:
    config = (project or {}).get("config") or {}
    settings = config.get("douyin_reup") or {}
    return bool(settings.get("keep_original_audio", True) or settings.get("add_bgm", True))
