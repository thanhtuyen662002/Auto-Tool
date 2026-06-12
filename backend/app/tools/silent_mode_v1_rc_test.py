from __future__ import annotations

import argparse
import io
import json
import sys
import traceback
import uuid
import wave
from collections import Counter
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from app import database
from app.modules.douyin_reup.douyin_folder_scanner import DouyinFolderScanner
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, DouyinVideoItem, TranslationResult
from app.modules.douyin_reup.subtitle_timing_guard import SubtitleBlock, parse_srt_blocks, write_srt_blocks
from app.modules.douyin_reup_presets import DouyinReupPresetService
from app.modules.final_output_qa import PlatformTarget
from app.modules.final_output_qa.export_pack_service import ExportPackService
from app.modules.final_output_qa.final_output_qa_service import FinalOutputQAService, build_final_qa_summary
from app.modules.hardsub_ocr import HardSubOCRResult, OCRSubtitleLine
from app.modules.silent_immersive_reup.silent_reup_pipeline import SilentReupPipeline
from app.modules.silent_immersive_reup.silent_reup_service import SilentReupService
from app.modules.subtitle_review import SubtitleReviewService
from app.utils.file_utils import ensure_dir, write_json
from app.version import APP_VERSION


if sys.stdout.encoding and sys.stdout.encoding.lower() not in {"utf-8", "utf8"}:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


class MockSilentOCRService:
    def extract_hardsub_to_srt(self, video_path: str, output_dir: str, _settings: DouyinReupSettings) -> HardSubOCRResult:
        target = ensure_dir(output_dir)
        source_path = target / "mock_ocr_source_zh.srt"
        lines = [
            OCRSubtitleLine(index=1, start_ms=0, end_ms=1800, text="厨房好物", confidence=0.94, frame_count=2),
            OCRSubtitleLine(index=2, start_ms=1800, end_ms=3800, text="收纳更方便", confidence=0.91, frame_count=2),
        ]
        write_srt_blocks(
            [SubtitleBlock(index=line.index, start=line.start_ms / 1000, end=line.end_ms / 1000, text=line.text) for line in lines],
            str(source_path),
        )
        debug_path = target / "mock_ocr_debug.json"
        write_json(debug_path, {"provider": "mock", "detected_line_count": len(lines), "average_confidence": 0.925})
        return HardSubOCRResult(
            video_path=video_path,
            provider="mock",
            language="ch",
            region_mode="bottom_auto",
            source_srt_path=str(source_path),
            debug_json_path=str(debug_path),
            frame_count=4,
            detected_line_count=len(lines),
            average_confidence=0.925,
            lines=lines,
            warnings=["Mock OCR enabled for Silent Mode RC QA."],
        )


class MockSilentTranslator:
    def translate_srt(self, source_srt_path: str, output_srt_path: str, **_kwargs: Any) -> TranslationResult:
        source = parse_srt_blocks(source_srt_path)
        translated = [
            SubtitleBlock(index=index, start=block.start, end=block.end, text=text)
            for index, (block, text) in enumerate(
                zip(source, ["Món hay cho căn bếp gọn hơn", "Sắp xếp tiện hơn mỗi ngày"], strict=False),
                start=1,
            )
        ]
        write_srt_blocks(translated, output_srt_path)
        return TranslationResult(
            source_srt_path=source_srt_path,
            translated_srt_path=output_srt_path,
            provider="mock",
            source_language="zh",
            target_language="vi",
            warnings=["Mock translation enabled for Silent Mode RC QA."],
        )


class MockSilentVoiceGenerator:
    warnings = ["Mock TTS enabled for Silent Mode RC QA."]

    def generate_voiceover(self, _script: Any, output_dir: str, **_kwargs: Any) -> str:
        output = ensure_dir(output_dir) / "silent_voiceover_mock.wav"
        with wave.open(str(output), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(b"\x00\x00" * 16000)
        return str(output)


def run_rc_test(args: argparse.Namespace) -> dict[str, Any]:
    started = perf_counter()
    result = _base_result()
    original_db_path = database.DB_PATH
    output_dir: Path | None = None
    logs: list[dict[str, str]] = []
    outputs: list[dict[str, Any]] = []
    qa_reports = []
    project_id = f"silent-v1-rc-{uuid.uuid4().hex[:8]}"
    job_id = f"{project_id}-job"

    try:
        config_path = _resolve_config(Path(args.config))
        raw = json.loads(config_path.read_text(encoding="utf-8-sig"))
        source_dir = _resolve_path(raw.get("source_folder") or "../../../sample_videos/silent_mode_v1_rc", config_path.parent)
        output_dir = ensure_dir(_resolve_path(raw.get("output_folder") or "../../outputs/silent_mode_v1_rc", config_path.parent))
        settings = _load_settings(raw, args)
        product_context = dict(raw.get("product_context") or {})
        if args.industry:
            product_context["industry"] = args.industry
        industry = str(product_context.get("industry") or "general_product")
        result.update(
            {
                "preset": settings.preset_id,
                "strategy": settings.silent_mode_strategy,
                "industry": industry,
                "project_name": raw.get("project_name") or "silent-v1-rc",
                "project_id": project_id,
                "job_id": job_id,
                "output_folder": str(output_dir),
            }
        )

        database.DB_PATH = output_dir / "silent_mode_v1_rc.db"
        database.init_db()
        database.create_project(project_id, _project_payload(raw, source_dir, output_dir, settings, product_context))
        database.create_job(job_id, project_id, preview_only=False, total_outputs=0)

        scan_started = perf_counter()
        scanner = DouyinFolderScanner()
        videos = scanner.scan_folder(str(source_dir))
        result["durations"]["scan_seconds"] = _elapsed(scan_started)
        result["total_videos"] = len(videos)
        result["warnings"].extend(scanner.errors)
        _log(logs, "info", f"Scanned {len(videos)} valid videos from {source_dir}.")
        if not videos:
            result["warnings"].append(f"No video files found in source folder: {source_dir}")
            result["status"] = "success_with_warnings"
            return _finish_and_write(result, started, output_dir, outputs, logs)
        database.update_job(job_id, total_outputs=len(videos), status="running", current_step="silent_detection")
        if args.scan_only:
            return _finish_and_write(result, started, output_dir, outputs, logs)

        pipeline = SilentReupPipeline(
            ocr_service=MockSilentOCRService() if args.mock_ocr else None,
            translator=MockSilentTranslator() if args.mock_ocr else None,
            voice_generator=MockSilentVoiceGenerator() if args.mock_tts else None,
        )
        service = SilentReupService(pipeline=pipeline)
        review_service = SubtitleReviewService()
        detect_started = perf_counter()
        detections: dict[str, Any] = {}
        for video in videos:
            try:
                detection = service.detector.detect(video.path)
                detections[video.path] = detection
                if not detection.has_speech:
                    result["silent_detected"] += 1
            except Exception as exc:
                result["warnings"].append(f"{video.filename}: speech detection failed: {_friendly_error(exc)}")
                result["failure_breakdown"]["speech_detection_failed"] += 1
        result["durations"]["silent_detection_seconds"] = _elapsed(detect_started)
        if args.detect_only:
            return _finish_and_write(result, started, output_dir, outputs, logs)

        for index, video in enumerate(videos, start=1):
            row_started = perf_counter()
            row: dict[str, Any] = {
                "index": index,
                "source_video": video.path,
                "status": "processing",
                "failed_step": None,
                "warnings": [],
                "errors": [],
            }
            video_dir = ensure_dir(output_dir / f"video_{index:03d}_{Path(video.path).stem}")
            try:
                plan_started = perf_counter()
                plan = service.build_plan(video.path, settings=settings, output_dir=str(video_dir), product_context=product_context)
                result["durations"]["planning_seconds"] += _elapsed(plan_started)
                if not plan.visual_segments:
                    row["failed_step"] = "visual_segmentation"
                    raise RuntimeError("Cannot create visual segments for this video.")
                if not plan.captions:
                    row["failed_step"] = "caption_generation"
                    raise RuntimeError("Cannot generate captions for this video.")
                result["plans_created"] += 1
                result["visual_segments_created"] += len(plan.visual_segments)
                result["visual_tag_reports_created"] += int(plan.visual_tag_report is not None)
                result["captions_generated"] += len(plan.captions)
                result["caption_sources"].update(caption.source for caption in plan.captions)
                result["recommended_industries"].update([plan.visual_tagging.recommended_industry])
                result["tag_confidences"].append(plan.visual_tagging.average_confidence)
                result["caption_quality_scores"].extend(
                    caption.quality_score for caption in plan.captions if caption.quality_score is not None
                )
                result["caption_quality_flagged"] += sum(1 for caption in plan.captions if caption.quality_needs_review)
                caption_srt = pipeline.write_caption_srt(plan, str(video_dir), f"video_{index:03d}_silent_vi.srt")
                row.update(
                    {
                        "status": "planned",
                        "silent_detected": not bool(getattr(detections.get(video.path), "has_speech", False)),
                        "silent_plan_file": pipeline.last_plan_path,
                        "visual_tag_report_file": str(video_dir / "visual_tag_report.json"),
                        "caption_generation_log_file": str(video_dir / "caption_generation_log.json"),
                        "translated_srt_file": caption_srt,
                        "caption_source": _caption_source(plan),
                        "visual_segments": len(plan.visual_segments),
                        "captions": len(plan.captions),
                        "warnings": list(plan.warnings),
                    }
                )

                create_review = not args.plan_only and (args.review_mode or settings.silent_review_before_render)
                if create_review:
                    review_started = perf_counter()
                    document = review_service.create_document_from_srt(
                        video_id=f"silent_v1_rc_{index:03d}",
                        video_path=video.path,
                        translated_srt_path=caption_srt,
                        source_srt_path=pipeline.last_ocr_source_srt_path,
                        project_id=project_id,
                        job_id=job_id,
                        source_language=settings.source_language,
                        target_language=settings.target_language,
                        source_type=_caption_source(plan),
                        context={
                            "reup_mode": "silent_immersive",
                            "silent_strategy": plan.strategy,
                            "silent_plan_file": pipeline.last_plan_path,
                            "caption_generation": plan.caption_generation.model_dump(mode="json"),
                            "visual_tagging": plan.visual_tagging.model_dump(mode="json"),
                            "product_context": product_context,
                            "settings_snapshot": settings.model_dump(mode="json"),
                        },
                    )
                    result["durations"]["review_document_seconds"] += _elapsed(review_started)
                    result["review_documents_created"] += 1
                    row["subtitle_review_document_id"] = document.id
                    row["status"] = "needs_review"

                if args.auto_render:
                    render_started = perf_counter()
                    rendered = pipeline.render_from_plan(plan, settings, str(video_dir))
                    result["durations"]["render_seconds"] += _elapsed(render_started)
                    if rendered.status != "success" or not rendered.output_video_path:
                        row["failed_step"] = "render"
                        raise RuntimeError("; ".join(rendered.errors) or "Render failed without an output video.")
                    result["rendered"] += 1
                    row.update({"status": "success", "path": rendered.output_video_path, "log_file": rendered.log_path})
                    if args.final_qa:
                        qa_started = perf_counter()
                        report = FinalOutputQAService().run_qa_for_output(
                            rendered.output_video_path,
                            PlatformTarget.tiktok,
                            video_id=f"silent_v1_rc_{index:03d}",
                            ass_path=rendered.caption_ass_path,
                            subtitle_expected=settings.burn_subtitle,
                            audio_expected=settings.keep_immersive_original_audio or settings.generate_voiceover_for_silent_video,
                            overlay_expected=settings.add_overlay,
                            report_path=str(video_dir / f"video_{index:03d}_final_qa.json"),
                        )
                        result["durations"]["final_qa_seconds"] += _elapsed(qa_started)
                        result["final_qa_checked"] += 1
                        qa_reports.append(report)
                        row["final_output_qa"] = {
                            "status": _qa_status(report.status),
                            "score": report.score,
                            "report_path": report.report_path,
                        }
            except Exception as exc:
                failed_step = row.get("failed_step") or _failure_step(exc)
                row.update({"status": "failed", "failed_step": failed_step})
                message = _friendly_error(exc)
                row["errors"].append(message)
                result["errors"].append(f"{video.filename}: {message}")
                result["failed"] += 1
                result["failure_breakdown"][f"{failed_step}_failed"] = result["failure_breakdown"].get(f"{failed_step}_failed", 0) + 1
                if args.debug:
                    row["traceback"] = traceback.format_exc()
            finally:
                row["duration_seconds"] = _elapsed(row_started)
                outputs.append(row)

        if qa_reports:
            write_json(output_dir / "final_qa_summary.json", build_final_qa_summary(qa_reports, PlatformTarget.tiktok))

        database.update_job(
            job_id,
            status="completed_with_errors" if result["failed"] else "completed",
            current_step="completed",
            progress=100,
            completed_outputs=len([row for row in outputs if row.get("status") != "failed"]),
            failed_outputs=result["failed"],
            output_folder=str(output_dir),
            results_json=json.dumps({"outputs": outputs}, ensure_ascii=False),
        )
        if args.export_pack:
            export_started = perf_counter()
            rendered_rows = [row for row in outputs if row.get("path")]
            if rendered_rows:
                pack = ExportPackService().create_export_pack_for_job(
                    job_id,
                    PlatformTarget.tiktok,
                    output_dir=str(output_dir / "export_pack"),
                )
                result["export_pack_created"] = True
                result["export_pack_path"] = pack.output_dir
            else:
                result["warnings"].append("Export Pack requires at least one rendered output. Use --auto-render.")
            result["durations"]["export_pack_seconds"] = _elapsed(export_started)

        result["status"] = _status(result)
    except Exception as exc:
        if args.debug:
            raise
        result["status"] = "failed"
        result["errors"].append(_friendly_error(exc))
    finally:
        database.DB_PATH = original_db_path

    if output_dir is not None:
        return _finish_and_write(result, started, output_dir, outputs, logs)
    result["runtime_seconds"] = _elapsed(started)
    return result


def _load_settings(raw: dict[str, Any], args: argparse.Namespace) -> DouyinReupSettings:
    payload = dict(raw.get("settings") or raw.get("douyin_reup") or {})
    preset_id = args.preset or payload.get("preset_id") or "silent_chill_immersive"
    settings = DouyinReupPresetService().apply_preset(preset_id, current_settings=payload)
    updates: dict[str, Any] = {"enabled": True, "enable_silent_immersive_mode": True, "preset_id": preset_id}
    if args.auto_render:
        updates.update({"silent_review_before_render": False, "auto_render_after_translation": True})
    return settings.model_copy(update=updates)


def _project_payload(
    raw: dict[str, Any],
    source: Path,
    output: Path,
    settings: DouyinReupSettings,
    product_context: dict[str, Any],
) -> dict[str, Any]:
    return {
        "project_name": raw.get("project_name") or "silent-v1-rc",
        "source_folder": str(source),
        "output_folder": str(output),
        "product_context": product_context,
        "douyin_reup": settings.model_dump(mode="json"),
    }


def _write_artifacts(
    output_dir: Path,
    result: dict[str, Any],
    outputs: list[dict[str, Any]],
    logs: list[dict[str, str]],
) -> None:
    caption_scores = result.pop("caption_quality_scores", [])
    tag_confidences = result.pop("tag_confidences", [])
    caption_sources = result.pop("caption_sources", Counter())
    recommended = result.pop("recommended_industries", Counter())
    serializable = dict(result)
    serializable["caption_sources"] = dict(caption_sources)
    serializable["visual_tagging"] = {
        "enabled": True,
        "average_confidence": round(sum(tag_confidences) / len(tag_confidences), 4) if tag_confidences else 0.0,
        "recommended_industries": dict(recommended),
    }
    serializable["caption_quality"] = {
        "average_score": round(sum(caption_scores) / len(caption_scores), 4) if caption_scores else 0.0,
        "flagged_lines": result.get("caption_quality_flagged", 0),
    }
    write_json(output_dir / "silent_mode_summary.json", serializable)
    write_json(output_dir / "douyin_reup_summary.json", {**serializable, "outputs": outputs})
    write_json(
        output_dir / "job_log.json",
        {
            "version": APP_VERSION,
            "mode": "silent_immersive",
            "preset_id": result.get("preset"),
            "strategy": result.get("strategy"),
            "industry": result.get("industry"),
            "status": result.get("status"),
            "steps": ["scan", "silent_detection", "planning", "visual_tagging", "caption_generation", "review", "render", "final_qa", "export_pack"],
            "failed_step": "rc_test" if result.get("status") == "failed" else None,
            "warnings": result.get("warnings", []),
            "errors": result.get("errors", []),
            "durations": result.get("durations", {}),
            "paths": {
                "output_folder": str(output_dir),
                "silent_mode_summary": str(output_dir / "silent_mode_summary.json"),
                "douyin_reup_summary": str(output_dir / "douyin_reup_summary.json"),
                "final_qa_summary": str(output_dir / "final_qa_summary.json") if (output_dir / "final_qa_summary.json").exists() else None,
                "export_manifest": str(output_dir / "export_pack" / "export_manifest.json") if (output_dir / "export_pack" / "export_manifest.json").exists() else None,
            },
            "logs": logs,
        },
    )
    result["caption_sources"] = dict(caption_sources)
    result["visual_tagging"] = serializable["visual_tagging"]
    result["caption_quality"] = serializable["caption_quality"]


def _finish_and_write(
    result: dict[str, Any],
    started: float,
    output_dir: Path,
    outputs: list[dict[str, Any]],
    logs: list[dict[str, str]],
) -> dict[str, Any]:
    result["runtime_seconds"] = _elapsed(started)
    result["durations"]["total_seconds"] = result["runtime_seconds"]
    result["warnings"] = _dedupe(result["warnings"])
    result["errors"] = _dedupe(result["errors"])
    if result["status"] == "success" and (result["warnings"] or result["errors"]):
        result["status"] = "success_with_warnings"
    _write_artifacts(output_dir, result, outputs, logs)
    return result


def _base_result() -> dict[str, Any]:
    return {
        "status": "success",
        "version": APP_VERSION,
        "mode": "silent_immersive",
        "preset": "silent_chill_immersive",
        "strategy": "chill_immersive",
        "industry": "general_product",
        "total_videos": 0,
        "silent_detected": 0,
        "plans_created": 0,
        "visual_segments_created": 0,
        "visual_tag_reports_created": 0,
        "captions_generated": 0,
        "review_documents_created": 0,
        "approved": 0,
        "rendered": 0,
        "final_qa_checked": 0,
        "export_pack_created": False,
        "failed": 0,
        "caption_sources": Counter(),
        "recommended_industries": Counter(),
        "tag_confidences": [],
        "caption_quality_scores": [],
        "caption_quality_flagged": 0,
        "failure_breakdown": {
            "speech_detection_failed": 0,
            "visual_segmentation_failed": 0,
            "caption_generation_failed": 0,
            "render_failed": 0,
        },
        "durations": {
            "scan_seconds": 0.0,
            "silent_detection_seconds": 0.0,
            "planning_seconds": 0.0,
            "review_document_seconds": 0.0,
            "render_seconds": 0.0,
            "final_qa_seconds": 0.0,
            "export_pack_seconds": 0.0,
        },
        "warnings": [],
        "errors": [],
    }


def _caption_source(plan: Any) -> str:
    sources = [caption.source for caption in plan.captions]
    if "ocr_translation" in sources:
        return "ocr_translation"
    return sources[0] if sources else "template"


def _status(result: dict[str, Any]) -> str:
    total = int(result.get("total_videos") or 0)
    failed = int(result.get("failed") or 0)
    if total and failed >= total:
        return "failed"
    if failed or result.get("warnings") or result.get("errors"):
        return "success_with_warnings"
    return "success"


def _failure_step(exc: Exception) -> str:
    lowered = str(exc).casefold()
    if "segment" in lowered:
        return "visual_segmentation"
    if "caption" in lowered:
        return "caption_generation"
    if "render" in lowered or "ffmpeg" in lowered:
        return "render"
    return "planning"


def _friendly_error(exc: Exception | str) -> str:
    text = " ".join(str(exc).split())
    lowered = text.casefold()
    if "ffmpeg" in lowered and "not found" in lowered:
        return "FFmpeg not found. Open Auto Tool once to install runtime dependencies or install FFmpeg manually."
    if "ffprobe" in lowered and "not found" in lowered:
        return "ffprobe not found. Install the complete FFmpeg package."
    if "source folder" in lowered or "cannot find" in lowered or "no such file" in lowered:
        return f"Source folder not found: {text}"
    if "permission" in lowered or "access is denied" in lowered:
        return f"Output folder permission denied: {text}"
    if "easyocr" in lowered or "paddleocr" in lowered:
        return "OCR provider missing. Install runtime dependencies or run with --mock-ocr."
    if "tts" in lowered or "voice" in lowered:
        return f"TTS provider failed. Retry with --mock-tts. Details: {text}"
    if "bgm" in lowered or "music" in lowered:
        return f"BGM folder or audio file is unavailable: {text}"
    if "segment" in lowered:
        return f"Cannot create visual segments: {text}"
    if "caption" in lowered:
        return f"Cannot generate captions: {text}"
    if "review" in lowered:
        return f"Cannot create review document: {text}"
    if "export" in lowered:
        return f"Export Pack creation failed: {text}"
    if "qa" in lowered:
        return f"Final QA failed: {text}"
    if "render" in lowered:
        return f"Render failed: {text}"
    return text or "Silent Mode RC test failed without a detailed error."


def _resolve_config(path: Path) -> Path:
    resolved = path.expanduser()
    if not resolved.is_absolute():
        resolved = (Path.cwd() / resolved).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Silent Mode RC config not found: {resolved}")
    return resolved


def _resolve_path(value: str | Path, base: Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def _elapsed(started: float) -> float:
    return round(perf_counter() - started, 3)


def _qa_status(value: Any) -> str:
    return str(getattr(value, "value", value))


def _log(logs: list[dict[str, str]], level: str, message: str) -> None:
    logs.append({"created_at": datetime.now().replace(microsecond=0).isoformat(), "level": level, "message": message})


def _dedupe(values: list[Any]) -> list[str]:
    return list(dict.fromkeys(text for value in values if (text := " ".join(str(value).split()))))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Silent / Immersive Product Reup v1.0 RC QA command.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--preset", choices=["silent_chill_immersive", "silent_product_voiceover", "silent_sales_recut"])
    parser.add_argument(
        "--industry",
        choices=["general_product", "home_goods", "kitchen_goods", "storage_organization", "desk_setup", "dorm_goods", "beauty_goods", "cleaning_goods"],
    )
    parser.add_argument("--scan-only", action="store_true")
    parser.add_argument("--detect-only", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--review-mode", action="store_true")
    parser.add_argument("--auto-render", action="store_true")
    parser.add_argument("--final-qa", action="store_true")
    parser.add_argument("--export-pack", action="store_true")
    parser.add_argument("--mock-ocr", action="store_true")
    parser.add_argument("--mock-tts", action="store_true")
    parser.add_argument("--debug", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_rc_test(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"success", "success_with_warnings"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
