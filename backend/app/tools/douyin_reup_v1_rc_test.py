from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from app import database
from app.modules.douyin_reup.douyin_folder_scanner import DouyinFolderScanner
from app.modules.douyin_reup.douyin_reup_service import DouyinReupService
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, DouyinVideoItem, SubtitleSourceResult, TranslationResult
from app.modules.douyin_reup.subtitle_timing_guard import SubtitleBlock, parse_srt_blocks, write_srt_blocks
from app.modules.douyin_reup_presets import DouyinReupPresetService
from app.modules.final_output_qa import PlatformTarget
from app.modules.final_output_qa.export_pack_service import ExportPackService
from app.modules.subtitle_review import SubtitleReviewService, SubtitleReviewStatus
from app.schemas.project_schema import ProjectConfig
from app.utils.file_utils import ensure_dir, write_json


VERSION = "1.0.0-rc1"


if sys.stdout.encoding and sys.stdout.encoding.lower() not in {"utf-8", "utf8"}:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


class MockSubtitleSourceDetector:
    def __init__(self, *, mock_asr: bool, mock_ocr: bool) -> None:
        from app.modules.douyin_reup.subtitle_source_detector import SubtitleSourceDetector

        self.delegate = SubtitleSourceDetector()
        self.mock_asr = mock_asr
        self.mock_ocr = mock_ocr

    def detect_source(
        self,
        video: DouyinVideoItem,
        settings: DouyinReupSettings,
        work_dir: str,
    ) -> SubtitleSourceResult:
        target_dir = ensure_dir(work_dir)
        for source_type in settings.subtitle_source_priority:
            if source_type == "sidecar_srt" and settings.use_sidecar_srt and video.sidecar_srt_path:
                source = Path(video.sidecar_srt_path)
                if source.exists() and source.stat().st_size > 0:
                    target = target_dir / f"{Path(video.path).stem}_source_{settings.source_language}.srt"
                    shutil.copy2(source, target)
                    return SubtitleSourceResult(
                        video_path=video.path,
                        source_type="sidecar_srt",
                        source_srt_path=str(target),
                        language=settings.source_language,
                    )
            if source_type == "ocr_hardsub" and self.mock_ocr and (
                settings.use_ocr_if_no_subtitle or settings.use_ocr_if_asr_failed
            ):
                path = _write_mock_source_srt(target_dir, video, "ocr")
                debug_path = target_dir / f"{Path(video.path).stem}_ocr_debug.json"
                write_json(
                    debug_path,
                    {
                        "provider": "mock",
                        "frame_count": 3,
                        "detected_line_count": 2,
                        "average_confidence": 0.91,
                    },
                )
                return SubtitleSourceResult(
                    video_path=video.path,
                    source_type="ocr_hardsub",
                    source_srt_path=str(path),
                    language=settings.source_language,
                    ocr_debug_json_path=str(debug_path),
                    ocr_frame_count=3,
                    ocr_detected_line_count=2,
                    ocr_average_confidence=0.91,
                    warnings=["Mock OCR đang bật cho RC test."],
                )
            if source_type == "asr" and self.mock_asr and settings.use_asr_if_no_subtitle:
                path = _write_mock_source_srt(target_dir, video, "asr")
                return SubtitleSourceResult(
                    video_path=video.path,
                    source_type="asr",
                    source_srt_path=str(path),
                    language=settings.source_language,
                    warnings=["Mock ASR đang bật cho RC test."],
                )
        return self.delegate.detect_source(video, settings, work_dir)


class MockSubtitleTranslator:
    def translate_srt(self, source_srt_path: str, output_srt_path: str, **kwargs: Any) -> TranslationResult:
        blocks = parse_srt_blocks(source_srt_path)
        if not blocks:
            raise RuntimeError(f"Invalid SRT format: {source_srt_path}")
        translated = [
            SubtitleBlock(
                index=index,
                start=block.start,
                end=block.end,
                text=f"Phụ đề kiểm thử tiếng Việt dòng {index}.",
            )
            for index, block in enumerate(blocks, start=1)
        ]
        write_srt_blocks(translated, output_srt_path)
        return TranslationResult(
            source_srt_path=source_srt_path,
            translated_srt_path=output_srt_path,
            provider="mock",
            source_language=str(kwargs.get("source_language") or "zh"),
            target_language=str(kwargs.get("target_language") or "vi"),
            warnings=["Mock translation đang bật cho RC test."],
        )


def run_rc_test(args: argparse.Namespace) -> dict[str, Any]:
    started = perf_counter()
    result = _base_result(args.preset or "config")
    original_db_path = database.DB_PATH
    output_folder: Path | None = None
    job_id = f"douyin-v1-rc-{uuid.uuid4().hex[:10]}"
    project_id = f"{job_id}-project"
    job_logs: list[dict[str, str]] = []

    try:
        config_path = _resolve_config_path(Path(args.config))
        config = _load_config(config_path, args)
        settings = config.douyin_reup or DouyinReupSettings(enabled=True)
        output_folder = ensure_dir(Path(config.output_folder))
        result["preset"] = settings.preset_id or args.preset
        result["output_folder"] = str(output_folder)
        result["job_id"] = job_id
        result["project_id"] = project_id

        database.DB_PATH = output_folder / "douyin_reup_v1_rc.db"
        database.init_db()
        database.create_project(project_id, config.model_dump(mode="json"))
        database.create_job(job_id, project_id, preview_only=False, total_outputs=0)

        scanner = DouyinFolderScanner()
        scan_started = perf_counter()
        media = scanner.scan_folder(config.source_folder)
        result["total_videos"] = len(media)
        result["scanned"] = len(media)
        result["warnings"].extend(scanner.errors)
        _log(job_logs, "info", f"Scanned {len(media)} valid videos in {perf_counter() - scan_started:.2f}s.")

        if not media:
            result["status"] = "success_with_warnings"
            result["warnings"].append(f"No video files found in source folder: {config.source_folder}")
            result = _finalize(result, started)
            _write_rc_artifacts(output_folder, result, job_logs)
            return result

        if args.scan_only:
            result["status"] = "success_with_warnings" if result["warnings"] else "success"
            result = _finalize(result, started)
            _write_rc_artifacts(output_folder, result, job_logs)
            return result

        database.update_job(job_id, total_outputs=len(media))
        service = DouyinReupService(
            source_detector=MockSubtitleSourceDetector(mock_asr=args.mock_asr, mock_ocr=args.mock_ocr)
            if args.mock_asr or args.mock_ocr
            else None,
            translator=MockSubtitleTranslator() if args.mock_translation else None,
        )
        summary = service.process_folder(
            config,
            project_id=project_id,
            job_id=job_id,
            log_callback=lambda level, message: _log(job_logs, level, message),
        )
        outputs = [item for item in summary.get("outputs", []) if isinstance(item, dict)]
        database.update_job(
            job_id,
            status="completed_with_errors" if int(summary.get("failed_outputs") or 0) else "completed",
            completed_outputs=int(summary.get("successful_outputs") or 0),
            failed_outputs=int(summary.get("failed_outputs") or 0),
            progress=100,
            current_step="completed",
            results_json=json.dumps({"summary": summary, "outputs": outputs}, ensure_ascii=False),
            output_folder=summary.get("output_folder"),
        )

        result.update(_summary_counts(summary))
        result["final_qa_checked"] = sum(1 for output in outputs if output.get("final_output_qa"))
        result["warnings"].extend(warning for output in outputs for warning in output.get("warnings", []))
        result["errors"].extend(error for output in outputs for error in output.get("errors", []))
        result["summary_file"] = summary.get("summary_file")
        result["output_folder"] = summary.get("output_folder") or result["output_folder"]

        if args.render_approved:
            render_result = _render_approved_documents(project_id, job_id, settings, Path(str(result["output_folder"])))
            result["approved"] = render_result["approved"]
            result["rendered"] += render_result["rendered"]
            result["failed"] += render_result["failed"]
            result["warnings"].extend(render_result["warnings"])
            result["errors"].extend(render_result["errors"])

        if args.export_pack:
            export_result = _create_export_pack(job_id)
            result["export_pack_created"] = export_result["created"]
            result["warnings"].extend(export_result["warnings"])
            result["errors"].extend(export_result["errors"])

        result["status"] = _status_from_result(result)
    except Exception as exc:
        if args.debug:
            raise
        result["status"] = "failed"
        result["errors"].append(_friendly_error(exc))
        if args.debug:
            result["traceback"] = traceback.format_exc()
        if output_folder:
            _write_rc_artifacts(output_folder, result, job_logs)
    finally:
        database.DB_PATH = original_db_path

    result = _finalize(result, started)
    artifact_folder = result.get("output_folder") or (str(output_folder) if output_folder else None)
    if artifact_folder:
        _write_rc_artifacts(Path(str(artifact_folder)), result, job_logs)
    return result


def _load_config(config_path: Path, args: argparse.Namespace) -> ProjectConfig:
    raw = json.loads(config_path.read_text(encoding="utf-8-sig"))
    base_dir = config_path.parent
    if "product" not in raw:
        raw = _minimal_to_project_config(raw)
    raw = dict(raw)
    raw["source_folder"] = str(_resolve_path(raw.get("source_folder") or "", base_dir, must_exist=True))
    raw["output_folder"] = str(_resolve_path(raw.get("output_folder") or "", base_dir, must_exist=False))
    settings_payload = dict(raw.get("douyin_reup") or {})
    preset_id = args.preset or settings_payload.get("preset_id") or "safe_review"
    settings = DouyinReupPresetService().apply_preset(preset_id, current_settings=settings_payload)
    settings = _apply_runtime_flags(settings, args)
    raw["douyin_reup"] = settings.model_dump(mode="json")
    return ProjectConfig.model_validate(raw)


def _apply_runtime_flags(settings: DouyinReupSettings, args: argparse.Namespace) -> DouyinReupSettings:
    updates: dict[str, Any] = {"enabled": True}
    if args.translate_only or args.review_mode:
        updates.update({"review_subtitles_before_render": True, "auto_render_after_translation": False})
    if args.auto_render:
        updates.update({"review_subtitles_before_render": False, "auto_render_after_translation": True})
    return settings.model_copy(update=updates)


def _minimal_to_project_config(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "project_name": raw.get("project_name") or "douyin-v1-rc",
        "source_folder": raw.get("source_folder") or "../../../sample_videos/douyin_reup_v1_rc",
        "output_folder": raw.get("output_folder") or "../../outputs/douyin_reup_v1_rc",
        "product": {
            "name": "Douyin Reup RC",
            "brand": "",
            "description": "Douyin Reup v1.0 RC test config.",
            "features": ["Scan", "Translate", "Review", "Render", "QA"],
            "cta": "Review output",
        },
        "render": {"output_count": 1, "duration": 30, "aspect_ratio": "9:16", "resolution": "1080x1920", "fps": 30},
        "effects": {"cut_intensity": 0, "speed_variation": 0, "grain": 0, "zoom_motion": 0, "overlay_height": 22, "subtitle_size": 54},
        "ai": {
            "text_model": raw.get("text_model") or "gemini-3.1-flash-lite",
            "tone": "subtitle_translator",
            "language": "vi",
            "gemini_api_keys": raw.get("gemini_api_keys") or [],
        },
        "douyin_reup": raw.get("settings") or raw.get("douyin_reup") or {},
    }


def _summary_counts(summary: dict[str, Any]) -> dict[str, Any]:
    outputs = [item for item in summary.get("outputs", []) if isinstance(item, dict)]
    return {
        "total_videos": int(summary.get("total_videos") or len(outputs)),
        "source_srt_created": len([output for output in outputs if output.get("source_srt_file")]),
        "translated": len([output for output in outputs if output.get("translated_srt_file")]),
        "review_documents_created": len([output for output in outputs if output.get("subtitle_review_document_id")]),
        "rendered": int(summary.get("rendered") or len([output for output in outputs if output.get("path")])),
        "failed": int(summary.get("failed_outputs") or 0),
    }


def _render_approved_documents(project_id: str, job_id: str, settings: DouyinReupSettings, output_root: Path) -> dict[str, Any]:
    from app.modules.douyin_reup.douyin_render_pipeline import DouyinRenderPipeline

    documents = SubtitleReviewService().list_documents(project_id=project_id, job_id=job_id, status="approved")
    if not documents:
        return {
            "approved": 0,
            "rendered": 0,
            "failed": 0,
            "warnings": ["Không có Subtitle Review document đã approve để render."],
            "errors": [],
        }
    pipeline = DouyinRenderPipeline()
    render_root = ensure_dir(output_root / "render_approved")
    rendered = 0
    failed = 0
    errors: list[str] = []
    for document in documents:
        try:
            if document.status != SubtitleReviewStatus.approved:
                continue
            pipeline.render_from_review_document(document.id, settings, str(render_root / document.id))
            rendered += 1
        except Exception as exc:
            failed += 1
            errors.append(_friendly_error(exc))
    return {"approved": len(documents), "rendered": rendered, "failed": failed, "warnings": [], "errors": errors}


def _create_export_pack(job_id: str) -> dict[str, Any]:
    try:
        pack = ExportPackService().create_export_pack_for_job(job_id, PlatformTarget.tiktok)
        return {"created": True, "warnings": [], "errors": [], "path": pack.output_dir}
    except Exception as exc:
        return {
            "created": False,
            "warnings": [f"Export Pack chưa được tạo: {_friendly_error(exc)}"],
            "errors": [],
        }


def _write_mock_source_srt(target_dir: Path, video: DouyinVideoItem, source_type: str) -> Path:
    duration = max(1.5, float(video.duration or 3.0))
    path = target_dir / f"{Path(video.path).stem}_source_zh_{source_type}.srt"
    midpoint = min(duration - 0.2, max(1.2, duration / 2))
    blocks = [
        SubtitleBlock(index=1, start=0.0, end=min(midpoint, duration), text="这是一个测试字幕。"),
        SubtitleBlock(index=2, start=min(midpoint, duration), end=duration, text="请检查翻译和时间轴。"),
    ]
    return Path(write_srt_blocks(blocks, str(path)))


def _write_rc_artifacts(output_folder: Path, result: dict[str, Any], job_logs: list[dict[str, str]]) -> None:
    ensure_dir(output_folder)
    write_json(
        output_folder / "job_log.json",
        {
            "version": VERSION,
            "status": result.get("status"),
            "preset_id": result.get("preset"),
            "failed_step": "rc_test" if result.get("status") == "failed" else None,
            "warnings": result.get("warnings", []),
            "errors": result.get("errors", []),
            "durations": {"runtime_seconds": result.get("runtime_seconds")},
            "paths": {
                "output_folder": str(output_folder),
                "summary_file": str(output_folder / "douyin_reup_summary.json"),
            },
            "logs": job_logs,
        },
    )
    if not (output_folder / "douyin_reup_summary.json").exists():
        write_json(
            output_folder / "douyin_reup_summary.json",
            {
                "version": VERSION,
                "status": result.get("status"),
                "total_videos": result.get("total_videos", 0),
                "source_srt_created": result.get("source_srt_created", 0),
                "translated": result.get("translated", 0),
                "review_documents_created": result.get("review_documents_created", 0),
                "rendered": result.get("rendered", 0),
                "failed": result.get("failed", 0),
                "warnings": result.get("warnings", []),
                "errors": result.get("errors", []),
            },
        )


def _base_result(preset: str) -> dict[str, Any]:
    return {
        "status": "success",
        "version": VERSION,
        "preset": preset,
        "total_videos": 0,
        "scanned": 0,
        "source_srt_created": 0,
        "translated": 0,
        "review_documents_created": 0,
        "approved": 0,
        "rendered": 0,
        "final_qa_checked": 0,
        "export_pack_created": False,
        "failed": 0,
        "warnings": [],
        "errors": [],
    }


def _status_from_result(result: dict[str, Any]) -> str:
    errors = [error for error in result.get("errors", []) if error]
    failed = int(result.get("failed") or 0)
    total = int(result.get("total_videos") or 0)
    if errors and failed >= max(1, total):
        return "failed"
    if failed or result.get("warnings") or errors:
        return "success_with_warnings"
    return "success"


def _finalize(result: dict[str, Any], started: float) -> dict[str, Any]:
    result["runtime_seconds"] = round(perf_counter() - started, 3)
    result["warnings"] = _dedupe(result.get("warnings", []))
    result["errors"] = _dedupe(result.get("errors", []))
    return result


def _log(logs: list[dict[str, str]], level: str, message: str) -> None:
    logs.append({"created_at": datetime.now().replace(microsecond=0).isoformat(), "level": level, "message": str(message)})


def _resolve_config_path(path: Path) -> Path:
    resolved = path.expanduser()
    if not resolved.is_absolute():
        resolved = (Path.cwd() / resolved).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Không tìm thấy config RC: {resolved}")
    return resolved


def _resolve_path(value: str | Path, base_dir: Path, *, must_exist: bool) -> Path:
    if not value:
        raise ValueError("Path không được để trống.")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    if must_exist and not path.exists():
        raise FileNotFoundError(f"Source folder not found: {path}")
    return path


def _friendly_error(exc: Exception | str) -> str:
    text = " ".join(str(exc).split())
    lowered = text.lower()
    if "ffmpeg" in lowered and "not found" in lowered:
        return "FFmpeg not found. Hãy cài FFmpeg hoặc mở app để Auto Tool tự kiểm tra runtime."
    if "ffprobe" in lowered and "not found" in lowered:
        return "ffprobe not found. Hãy cài FFmpeg đầy đủ."
    if "source folder" in lowered or "no such file" in lowered:
        return text
    if "faster-whisper" in lowered or "faster_whisper" in lowered:
        return "faster-whisper not installed hoặc model ASR chưa sẵn sàng. Có thể chạy RC với --mock-asr."
    if "paddleocr" in lowered or "easyocr" in lowered:
        return "OCR provider chưa sẵn sàng. Có thể chạy RC với --mock-ocr."
    if "gemini" in lowered:
        return f"Gemini translation failed. Có thể chạy RC với --mock-translation. Chi tiết: {text}"
    if "invalid srt" in lowered:
        return f"Invalid SRT format: {text}"
    if "permission" in lowered or "access is denied" in lowered:
        return f"Output folder permission denied: {text}"
    if "export" in lowered:
        return f"Export pack creation failed: {text}"
    if "render" in lowered:
        return f"Render failed: {text}"
    if "qa" in lowered:
        return f"Final QA failed: {text}"
    return text or "RC test failed without a detailed error."


def _dedupe(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        text = " ".join(str(value).split())
        if not text or text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
    return cleaned


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Douyin Reup v1.0 RC QA command.")
    parser.add_argument("--config", required=True, help="Path to RC config JSON.")
    parser.add_argument("--preset", choices=["safe_review", "fast_auto", "ocr_priority", "voice_priority", "clean_subtitle_only", "music_recut"])
    parser.add_argument("--scan-only", action="store_true")
    parser.add_argument("--translate-only", action="store_true")
    parser.add_argument("--review-mode", action="store_true")
    parser.add_argument("--auto-render", action="store_true")
    parser.add_argument("--render-approved", action="store_true")
    parser.add_argument("--final-qa", action="store_true")
    parser.add_argument("--export-pack", action="store_true")
    parser.add_argument("--mock-asr", action="store_true")
    parser.add_argument("--mock-ocr", action="store_true")
    parser.add_argument("--mock-translation", action="store_true")
    parser.add_argument("--debug", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_rc_test(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"success", "success_with_warnings"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
