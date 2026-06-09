from __future__ import annotations

import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from app.modules.douyin_reup.douyin_folder_scanner import DouyinFolderScanner
from app.modules.douyin_reup.douyin_render_pipeline import DouyinRenderPipeline
from app.modules.douyin_reup.douyin_schema import (
    DouyinOutputResult,
    DouyinReupSettings,
    DouyinReupSummary,
    DouyinVideoItem,
    TranslationResult,
)
from app.modules.douyin_reup.subtitle_source_detector import SubtitleSourceDetector
from app.modules.douyin_reup.subtitle_timing_guard import SubtitleTimingGuard
from app.modules.douyin_reup.subtitle_translator import SubtitleTranslator
from app.schemas.project_schema import ProjectConfig
from app.utils.file_utils import ensure_dir, write_json

ProgressCallback = Callable[[dict[str, Any]], None]
LogCallback = Callable[[str, str], None]


class DouyinReupService:
    def __init__(
        self,
        scanner: DouyinFolderScanner | None = None,
        source_detector: SubtitleSourceDetector | None = None,
        translator: SubtitleTranslator | None = None,
        timing_guard: SubtitleTimingGuard | None = None,
        render_pipeline: DouyinRenderPipeline | None = None,
    ) -> None:
        self.scanner = scanner or DouyinFolderScanner()
        self.source_detector = source_detector or SubtitleSourceDetector()
        self.translator = translator or SubtitleTranslator()
        self.timing_guard = timing_guard or SubtitleTimingGuard()
        self.render_pipeline = render_pipeline or DouyinRenderPipeline()

    def process_folder(
        self,
        config: ProjectConfig,
        progress_callback: ProgressCallback | None = None,
        log_callback: LogCallback | None = None,
    ) -> dict[str, Any]:
        settings = config.douyin_reup or DouyinReupSettings(enabled=True)
        if not settings.enabled:
            settings = settings.model_copy(update={"enabled": True})

        created_at = datetime.now().replace(microsecond=0)
        output_root = ensure_dir(
            Path(config.output_folder) / f"{config.project_name}-douyin-reup-{created_at.strftime('%Y-%m-%d-%H%M%S')}"
        )
        _log(log_callback, "info", f"Bắt đầu xử lý Douyin Reup: {output_root}")

        videos = self._select_videos(self.scanner.scan_folder(config.source_folder), settings)
        total = len(videos)
        if total == 0:
            raise RuntimeError(f"Không tìm thấy video hợp lệ trong thư mục Douyin: {config.source_folder}")

        outputs: list[DouyinOutputResult] = []
        subtitle_sources: Counter[str] = Counter()
        completed = 0
        failed = 0

        _progress(progress_callback, total, completed, failed, "scanned", 5)
        for index, video in enumerate(videos, start=1):
            _progress(progress_callback, total, completed, failed, f"douyin_video_{index}", _progress_percent(index - 1, total))
            _log(log_callback, "info", f"Đang xử lý Douyin video {index}/{total}: {video.filename}")
            try:
                output = self._process_one_video(
                    index=index,
                    video=video,
                    config=config,
                    settings=settings,
                    output_root=output_root,
                )
                outputs.append(output)
                subtitle_sources.update([output.subtitle_source or "none"])
                if output.status == "success":
                    completed += 1
                else:
                    failed += 1
                    _log(log_callback, "warning", f"Video {index} lỗi: {'; '.join(output.errors)}")
            except Exception as exc:
                failed += 1
                output = self._failed_output(index, video, output_root, str(exc))
                outputs.append(output)
                _log(log_callback, "error", f"Video {index} thất bại: {exc}")

            _progress(progress_callback, total, completed, failed, f"douyin_video_{index}_done", _progress_percent(index, total))

        summary = DouyinReupSummary(
            project_name=config.project_name,
            output_folder=str(output_root),
            total_videos=len(videos),
            processed_outputs=len(outputs),
            successful_outputs=completed,
            failed_outputs=failed,
            warnings_count=sum(len(output.warnings) for output in outputs),
            subtitle_sources=dict(subtitle_sources),
            failed_items=[
                {"index": output.index, "reason": "; ".join(output.errors)[:300]}
                for output in outputs
                if output.status != "success"
            ],
            outputs=outputs,
        )
        summary_file = output_root / "douyin_reup_summary.json"
        summary = summary.model_copy(update={"summary_file": str(summary_file)})
        write_json(summary_file, summary.model_dump(mode="json"))
        _progress(progress_callback, total, completed, failed, "completed", 100)
        _log(log_callback, "info", f"Đã ghi tổng kết Douyin Reup: {summary_file}")
        return summary.model_dump(mode="json")

    def _process_one_video(
        self,
        index: int,
        video: DouyinVideoItem,
        config: ProjectConfig,
        settings: DouyinReupSettings,
        output_root: Path,
    ) -> DouyinOutputResult:
        video_dir = ensure_dir(output_root / f"video_{index:03d}")
        log_path = video_dir / f"video_{index:03d}_log.json"
        warnings = list(video.warnings)
        errors: list[str] = []
        started_at = datetime.now().replace(microsecond=0)
        steps: list[dict[str, str]] = []

        try:
            source_result = self.source_detector.detect_source(video, settings, str(video_dir))
            warnings.extend(source_result.warnings)
            if source_result.source_type == "none" or not source_result.source_srt_path:
                errors.extend(source_result.errors)
                raise RuntimeError("; ".join(errors) or "Không tìm thấy subtitle nguồn.")
            steps.append({"name": "detect_subtitle_source", "status": "success", "message": source_result.source_type})

            translated_path = video_dir / f"video_{index:03d}_{settings.target_language}.srt"
            translation = self.translator.translate_srt(
                source_result.source_srt_path,
                str(translated_path),
                source_language=settings.source_language,
                target_language=settings.target_language,
                provider=settings.translation_provider,
                model_name=config.ai.text_model,
                api_keys=config.ai.gemini_api_keys,
            )
            warnings.extend(translation.warnings)
            steps.append({"name": "translate_subtitle", "status": "success", "message": translation.provider})

            fixed_srt_path = video_dir / f"video_{index:03d}_{settings.target_language}_fixed.srt"
            subtitle_offset = settings.asr_subtitle_offset_seconds if source_result.source_type == "asr" else 0.0
            fixed_srt = self.timing_guard.guard_timing(
                translation.translated_srt_path,
                target_duration=video.duration,
                output_path=str(fixed_srt_path),
                time_offset_seconds=subtitle_offset,
            )
            translation = translation.model_copy(update={"translated_srt_path": fixed_srt})
            steps.append({"name": "guard_subtitle_timing", "status": "success", "message": ""})

            render_payload = self.render_pipeline.render_video_with_translated_subtitle(
                video=video,
                translation_result=translation,
                settings=settings,
                output_dir=str(video_dir),
                output_name=f"douyin_{index:03d}.mp4",
            )
            warnings.extend(render_payload.get("warnings") or [])
            errors.extend(render_payload.get("errors") or [])
            steps.append({"name": "render_final_video", "status": "success", "message": ""})

            output = DouyinOutputResult(
                index=index,
                path=str(render_payload["path"]),
                status="success",
                source_video=video.path,
                subtitle_source=source_result.source_type,
                source_srt_file=source_result.source_srt_path,
                translated_srt_file=fixed_srt,
                subtitle_ass_file=render_payload.get("subtitle_ass_file"),
                overlay_file=render_payload.get("overlay_file"),
                bgm_file=render_payload.get("bgm_file"),
                log_file=str(log_path),
                duration=render_payload.get("duration"),
                warnings=_dedupe(warnings),
                errors=_dedupe(errors),
            )
            return output
        except Exception as exc:
            errors.append(str(exc))
            steps.append({"name": "process_video", "status": "failed", "message": str(exc)})
            return DouyinOutputResult(
                index=index,
                path="",
                status="failed",
                source_video=video.path,
                log_file=str(log_path),
                warnings=_dedupe(warnings),
                errors=_dedupe(errors),
            )
        finally:
            finished_at = datetime.now().replace(microsecond=0)
            payload = {
                "index": index,
                "status": "success" if not errors else "failed",
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "duration_seconds": max(0.0, (finished_at - started_at).total_seconds()),
                "source_video": video.path,
                "steps": steps,
                "warnings": _dedupe(warnings),
                "errors": _dedupe(errors),
            }
            write_json(log_path, payload)

    def _select_videos(self, videos: list[DouyinVideoItem], settings: DouyinReupSettings) -> list[DouyinVideoItem]:
        if settings.process_mode == "selected":
            selected = {str(Path(path).expanduser().resolve()).lower() for path in settings.selected_video_paths}
            videos = [video for video in videos if str(Path(video.path).expanduser().resolve()).lower() in selected]
        if settings.process_mode == "first_n" and settings.max_videos:
            videos = videos[: settings.max_videos]
        elif settings.max_videos:
            videos = videos[: settings.max_videos]
        return videos

    def _failed_output(self, index: int, video: DouyinVideoItem, output_root: Path, reason: str) -> DouyinOutputResult:
        video_dir = ensure_dir(output_root / f"video_{index:03d}")
        log_path = video_dir / f"video_{index:03d}_log.json"
        try:
            shutil.copy2(video.path, video_dir / "source.mp4")
        except OSError:
            pass
        write_json(
            log_path,
            {
                "index": index,
                "status": "failed",
                "source_video": video.path,
                "steps": [{"name": "process_video", "status": "failed", "message": reason}],
                "warnings": video.warnings,
                "errors": [reason],
            },
        )
        return DouyinOutputResult(
            index=index,
            path="",
            status="failed",
            source_video=video.path,
            log_file=str(log_path),
            warnings=video.warnings,
            errors=[reason],
        )


def _progress(
    callback: ProgressCallback | None,
    total: int,
    completed: int,
    failed: int,
    current_step: str,
    progress: int,
) -> None:
    if not callback:
        return
    callback(
        {
            "current_step": current_step,
            "progress": progress,
            "total_outputs": total,
            "completed_outputs": completed,
            "failed_outputs": failed,
        }
    )


def _log(callback: LogCallback | None, level: str, message: str) -> None:
    if callback:
        callback(level, message)


def _progress_percent(done: int, total: int) -> int:
    if total <= 0:
        return 100
    return max(5, min(99, int((done / total) * 95) + 5))


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        text = " ".join(str(value).split())
        if not text or text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
    return cleaned
