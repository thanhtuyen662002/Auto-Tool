from __future__ import annotations

import argparse
import io
import json
import sys
import uuid
from pathlib import Path
from time import perf_counter
from typing import Any

from app import database
from app.modules.douyin_reup.douyin_folder_scanner import DouyinFolderScanner
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings
from app.modules.final_output_qa import PlatformTarget
from app.modules.final_output_qa.export_pack_service import ExportPackService
from app.modules.final_output_qa.final_output_qa_service import FinalOutputQAService
from app.modules.silent_immersive_reup.silent_reup_service import SilentReupService
from app.modules.subtitle_review import SubtitleReviewService
from app.utils.file_utils import ensure_dir


if sys.stdout.encoding and sys.stdout.encoding.lower() not in {"utf-8", "utf8"}:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def run_e2e(args: argparse.Namespace) -> dict[str, Any]:
    started = perf_counter()
    result = _empty_result()
    original_db_path = database.DB_PATH
    try:
        config_path = _resolve_config(Path(args.config))
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        source = _resolve_path(raw.get("source_folder") or "../../../sample_videos/silent_mode_test_pack", config_path.parent)
        output = ensure_dir(_resolve_path(raw.get("output_folder") or "../../outputs/silent_mode_test_pack", config_path.parent))
        settings = DouyinReupSettings.model_validate(raw.get("settings") or {})
        settings = _settings_for_args(settings, args)
        product_context = dict(raw.get("product_context") or {})
        scanner = DouyinFolderScanner()
        videos = scanner.scan_folder(str(source))
        result.update({"total_videos": len(videos), "warnings": list(scanner.errors), "output_folder": str(output)})
        result["strategy"] = settings.silent_mode_strategy
        if not videos:
            result["warnings"].append(f"Không tìm thấy video hợp lệ trong folder: {source}")
        if args.scan_only:
            return _finish(result, started)

        service = SilentReupService()
        detections = []
        for video in videos:
            detection = service.detector.detect(video.path)
            detections.append(detection)
            if not detection.has_speech:
                result["silent_detected"] += 1
        if args.detect_only:
            return _finish(result, started)

        database.DB_PATH = output / "silent_mode_e2e.db"
        database.init_db()
        review_service = SubtitleReviewService()
        output_rows: list[dict[str, Any]] = []
        for index, video in enumerate(videos, start=1):
            try:
                video_dir = ensure_dir(output / f"video_{index:03d}")
                plan = service.build_plan(
                    video.path,
                    settings=settings,
                    output_dir=str(video_dir),
                    product_context=product_context,
                )
                result["plans_created"] += 1
                caption_srt = service.pipeline.write_caption_srt(plan, str(video_dir), f"video_{index:03d}_silent_vi.srt")
                document_id = None
                if args.review_mode:
                    document = review_service.create_document_from_srt(
                        video_id=f"silent_e2e_{index:03d}",
                        video_path=video.path,
                        translated_srt_path=caption_srt,
                        source_srt_path=service.pipeline.last_ocr_source_srt_path,
                        source_type=_caption_source(plan),
                        context={
                            "reup_mode": "silent_immersive",
                            "silent_strategy": plan.strategy,
                            "silent_plan_file": service.pipeline.last_plan_path,
                            "caption_generation": plan.caption_generation.model_dump(mode="json"),
                            "product_context": product_context,
                            "settings_snapshot": settings.model_dump(mode="json"),
                        },
                    )
                    document_id = document.id
                    result["review_documents_created"] += 1

                row = {
                    "index": index,
                    "path": "",
                    "status": "needs_review" if document_id else "planned",
                    "source_video": video.path,
                    "translated_srt_file": caption_srt,
                    "subtitle_review_document_id": document_id,
                    "silent_plan_file": service.pipeline.last_plan_path,
                    "caption_source": _caption_source(plan),
                    "silent_caption_generation": plan.caption_generation.model_dump(mode="json"),
                    "warnings": plan.warnings,
                    "errors": [],
                }
                if args.auto_render:
                    rendered = service.pipeline.render_from_plan(plan, settings, str(video_dir))
                    if rendered.status != "success" or not rendered.output_video_path:
                        raise RuntimeError("; ".join(rendered.errors) or "Silent render did not create an output video.")
                    row.update({"path": rendered.output_video_path, "status": "success", "log_file": rendered.log_path})
                    result["rendered"] += 1
                    if args.final_qa:
                        report = FinalOutputQAService().run_qa_for_output(
                            rendered.output_video_path,
                            PlatformTarget.tiktok,
                            video_id=f"silent_e2e_{index:03d}",
                            ass_path=rendered.caption_ass_path,
                            subtitle_expected=settings.burn_subtitle,
                            audio_expected=True,
                            overlay_expected=settings.add_overlay,
                            report_path=str(video_dir / f"video_{index:03d}_final_qa.json"),
                        )
                        row["final_output_qa"] = {
                            "status": str(getattr(report.status, "value", report.status)),
                            "score": report.score,
                            "report_path": report.report_path,
                            "issues": [issue.model_dump(mode="json") for issue in report.issues],
                        }
                        if str(getattr(report.status, "value", report.status)) == "passed":
                            result["final_qa_passed"] += 1
                output_rows.append(row)
            except Exception as exc:
                result["failed"] += 1
                result["errors"].append(f"{video.filename}: {_friendly_error(exc)}")

        if args.export_pack:
            rendered_rows = [row for row in output_rows if row.get("path")]
            if rendered_rows:
                project_id = f"silent-e2e-{uuid.uuid4().hex[:8]}"
                job_id = f"{project_id}-job"
                database.create_project(project_id, _project_payload(raw, source, output, settings))
                database.create_job(job_id, project_id, preview_only=False, total_outputs=len(rendered_rows))
                database.update_job(
                    job_id,
                    status="completed",
                    results_json=json.dumps({"outputs": rendered_rows, "summary": {}}, ensure_ascii=False),
                )
                pack = ExportPackService().create_export_pack_for_job(
                    job_id,
                    PlatformTarget.tiktok,
                    output_dir=str(output / "export_pack"),
                )
                result["export_packs"] = 1
                result["export_pack_path"] = pack.output_dir
            else:
                result["warnings"].append("Export Pack requires --auto-render outputs.")
        result["status"] = _status(result)
    except Exception as exc:
        if args.debug:
            raise
        result["status"] = "failed"
        result["errors"].append(_friendly_error(exc))
    finally:
        database.DB_PATH = original_db_path
    return _finish(result, started)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Silent / Immersive Mode real batch E2E QA.")
    parser.add_argument("--config", required=True)
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


def _settings_for_args(settings: DouyinReupSettings, args: argparse.Namespace) -> DouyinReupSettings:
    updates: dict[str, Any] = {"enabled": True, "enable_silent_immersive_mode": True}
    if args.mock_ocr:
        updates["use_ocr_if_no_subtitle"] = False
    if args.mock_tts:
        updates["generate_voiceover_for_silent_video"] = False
    return settings.model_copy(update=updates)


def _project_payload(raw: dict[str, Any], source: Path, output: Path, settings: DouyinReupSettings) -> dict[str, Any]:
    context = raw.get("product_context") or {}
    return {
        "project_name": raw.get("project_name") or "silent-mode-e2e",
        "source_folder": str(source),
        "output_folder": str(output),
        "product": {
            "name": context.get("product_name") or "Silent Mode QA",
            "brand": "",
            "description": "Silent Mode real batch QA",
            "features": context.get("features") or ["Caption template QA"],
            "cta": context.get("cta") or "Xem thêm",
        },
        "render": {"output_count": 1, "duration": 8, "aspect_ratio": "9:16", "resolution": settings.resolution, "fps": settings.fps},
        "effects": {"cut_intensity": 0, "speed_variation": 0, "grain": 0, "zoom_motion": 0, "overlay_height": 22, "subtitle_size": 54},
        "ai": {"text_model": "gemini-3.1-flash-lite", "tone": "natural", "language": "vi", "gemini_api_keys": []},
        "industry": {"preset_id": context.get("industry") or "general_product"},
        "douyin_reup": settings.model_dump(mode="json"),
    }


def _caption_source(plan: Any) -> str:
    sources = [caption.source for caption in plan.captions]
    return "ocr_translation" if "ocr_translation" in sources else (sources[0] if sources else "template")


def _resolve_config(path: Path) -> Path:
    resolved = path.expanduser()
    if not resolved.is_absolute():
        resolved = (Path.cwd() / resolved).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Không tìm thấy config Silent E2E: {resolved}")
    return resolved


def _resolve_path(value: str | Path, base: Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def _friendly_error(exc: Exception) -> str:
    text = " ".join(str(exc).split())
    if "ffmpeg" in text.casefold():
        return f"FFmpeg error: {text}"
    if "easyocr" in text.casefold() or "paddleocr" in text.casefold():
        return f"OCR error: {text}"
    return text or "Silent E2E failed without a detailed error."


def _empty_result() -> dict[str, Any]:
    return {
        "status": "success",
        "mode": "silent_immersive",
        "strategy": "chill_immersive",
        "total_videos": 0,
        "silent_detected": 0,
        "plans_created": 0,
        "review_documents_created": 0,
        "rendered": 0,
        "final_qa_passed": 0,
        "export_packs": 0,
        "failed": 0,
        "warnings": [],
        "errors": [],
    }


def _status(result: dict[str, Any]) -> str:
    if result["failed"] >= result["total_videos"] and result["total_videos"]:
        return "failed"
    if result["failed"] or result["warnings"] or result["errors"]:
        return "success_with_warnings"
    return "success"


def _finish(result: dict[str, Any], started: float) -> dict[str, Any]:
    result["runtime_seconds"] = round(perf_counter() - started, 3)
    result["warnings"] = list(dict.fromkeys(result["warnings"]))
    result["errors"] = list(dict.fromkeys(result["errors"]))
    if result["status"] == "success" and (result["warnings"] or result["errors"]):
        result["status"] = "success_with_warnings"
    return result


def main() -> int:
    args = build_parser().parse_args()
    result = run_e2e(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"success", "success_with_warnings"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
