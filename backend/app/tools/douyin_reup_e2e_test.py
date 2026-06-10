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
from app.modules.douyin_reup.douyin_render_pipeline import DouyinRenderPipeline
from app.modules.douyin_reup.douyin_reup_service import DouyinReupService
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, TranslationResult
from app.modules.subtitle_review import SubtitleReviewService, SubtitleReviewStatus
from app.schemas.project_schema import ProjectConfig
from app.utils.file_utils import ensure_dir


if sys.stdout.encoding and sys.stdout.encoding.lower() not in {"utf-8", "utf8"}:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


class MockSubtitleTranslator:
    def translate_srt(self, source_srt_path: str, output_srt_path: str, **kwargs: Any) -> TranslationResult:
        source = Path(source_srt_path)
        target = Path(output_srt_path)
        ensure_dir(target.parent)
        target.write_text(source.read_text(encoding="utf-8-sig", errors="replace"), encoding="utf-8")
        return TranslationResult(
            source_srt_path=str(source),
            translated_srt_path=str(target),
            provider="mock",
            source_language=str(kwargs.get("source_language") or "zh"),
            target_language=str(kwargs.get("target_language") or "vi"),
            warnings=["Mock translation enabled: copied source SRT to translated SRT."],
        )


def run_e2e(args: argparse.Namespace) -> dict[str, Any]:
    started = perf_counter()
    result = _empty_result()
    config_path = _resolve_config_path(Path(args.config))
    original_db_path = database.DB_PATH

    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        config = _build_config(raw, config_path.parent)
        settings = _runtime_settings(config.douyin_reup or DouyinReupSettings(enabled=True), args)
        source_folder = _resolve_path(config.source_folder, config_path.parent, must_exist=False)
        output_folder = ensure_dir(_resolve_path(config.output_folder, config_path.parent, must_exist=False))
        config = config.model_copy(
            update={
                "source_folder": str(source_folder),
                "output_folder": str(output_folder),
                "douyin_reup": settings,
            }
        )

        scanner = DouyinFolderScanner()
        media = scanner.scan_folder(config.source_folder)
        result["total_videos"] = len(media)
        result["warnings"].extend(scanner.errors)
        if not media:
            result["warnings"].append(f"Không tìm thấy video hợp lệ trong folder: {config.source_folder}")
        if args.scan_only:
            result["status"] = "success" if media else "success_with_warnings"
            result["failed"] = scanner.invalid_files
            return _finalize(result, started)

        database.DB_PATH = output_folder / "douyin_reup_e2e.db"
        database.init_db()
        project_id = f"douyin-e2e-{uuid.uuid4().hex[:10]}"
        job_id = f"{project_id}-job"
        database.create_project(project_id, config.model_dump(mode="json"))
        translator = MockSubtitleTranslator() if args.mock_translation else None
        service = DouyinReupService(translator=translator) if translator else DouyinReupService()
        summary = service.process_folder(config, project_id=project_id, job_id=job_id)
        outputs = summary.get("outputs", [])
        result.update(
            {
                "status": _status_from_summary(summary),
                "total_videos": int(summary.get("total_videos") or len(media)),
                "source_srt_created": len([output for output in outputs if output.get("source_srt_file")]),
                "translated": len([output for output in outputs if output.get("translated_srt_file")]),
                "review_documents_created": len([output for output in outputs if output.get("subtitle_review_document_id")]),
                "approved": 0,
                "rendered": int(summary.get("rendered") or 0),
                "failed": int(summary.get("failed_outputs") or 0),
                "warnings": [*result["warnings"], *[warning for output in outputs for warning in output.get("warnings", [])]],
                "errors": [error for output in outputs for error in output.get("errors", [])],
                "summary_file": summary.get("summary_file"),
                "output_folder": summary.get("output_folder"),
            }
        )

        if args.render_approved:
            render_result = _render_approved(raw, config, output_folder, result)
            result["rendered"] += render_result["rendered"]
            result["failed"] += render_result["failed"]
            result["errors"].extend(render_result["errors"])

    except Exception as exc:
        if args.debug:
            raise
        result["status"] = "failed"
        result["errors"].append(_friendly_error(exc))
    finally:
        database.DB_PATH = original_db_path

    return _finalize(result, started)


def _render_approved(raw: dict[str, Any], config: ProjectConfig, output_folder: Path, result: dict[str, Any]) -> dict[str, Any]:
    job_id = raw.get("job_id")
    project_id = raw.get("project_id")
    documents = SubtitleReviewService().list_documents(project_id=project_id, job_id=job_id, status="approved")
    if not documents:
        result["warnings"].append("Không có Subtitle Review Document đã approve để render.")
        return {"rendered": 0, "failed": 0, "errors": []}
    pipeline = DouyinRenderPipeline()
    render_root = ensure_dir(output_folder / f"douyin_e2e_render_approved_{uuid.uuid4().hex[:8]}")
    rendered = 0
    failed = 0
    errors: list[str] = []
    for index, document in enumerate(documents, start=1):
        try:
            if document.status != SubtitleReviewStatus.approved:
                continue
            pipeline.render_from_review_document(document.id, config.douyin_reup or DouyinReupSettings(enabled=True), str(render_root / f"video_{index:03d}"))
            rendered += 1
        except Exception as exc:
            failed += 1
            errors.append(_friendly_error(exc))
    return {"rendered": rendered, "failed": failed, "errors": errors}


def _build_config(raw: dict[str, Any], base_dir: Path) -> ProjectConfig:
    if "product" in raw and "render" in raw and "effects" in raw and "ai" in raw:
        return ProjectConfig.model_validate(raw)
    return ProjectConfig.model_validate(
        {
            "project_name": raw.get("project_name") or "douyin-reup-e2e",
            "source_folder": str(_resolve_path(raw.get("source_folder") or "../../sample_videos/douyin_reup_test_pack", base_dir, must_exist=False)),
            "output_folder": str(_resolve_path(raw.get("output_folder") or "../../examples/outputs/douyin_reup_e2e", base_dir, must_exist=False)),
            "product": {
                "name": "Douyin Reup E2E",
                "brand": "",
                "description": "Real batch QA config",
                "features": ["Douyin subtitle review"],
                "cta": "Xem thêm",
            },
            "render": {"output_count": 1, "duration": 30, "aspect_ratio": "9:16", "resolution": "1080x1920", "fps": 30},
            "effects": {
                "cut_intensity": 0,
                "speed_variation": 0,
                "grain": 0,
                "zoom_motion": 0,
                "overlay_height": 22,
                "subtitle_size": 54,
            },
            "ai": {"text_model": raw.get("text_model") or "gemini-3.1-flash-lite", "tone": "translator", "language": "vi", "gemini_api_keys": raw.get("gemini_api_keys") or []},
            "douyin_reup": raw.get("settings") or DouyinReupSettings(enabled=True).model_dump(mode="json"),
        }
    )


def _runtime_settings(settings: DouyinReupSettings, args: argparse.Namespace) -> DouyinReupSettings:
    updates: dict[str, Any] = {"enabled": True}
    if args.skip_asr:
        updates["use_asr_if_no_subtitle"] = False
    if args.review_mode or args.translate_only:
        updates.update({"review_subtitles_before_render": True, "auto_render_after_translation": False})
    if args.auto_render:
        updates.update({"review_subtitles_before_render": False, "auto_render_after_translation": True})
    return settings.model_copy(update=updates)


def _empty_result() -> dict[str, Any]:
    return {
        "status": "success",
        "total_videos": 0,
        "source_srt_created": 0,
        "translated": 0,
        "review_documents_created": 0,
        "approved": 0,
        "rendered": 0,
        "failed": 0,
        "warnings": [],
        "errors": [],
    }


def _status_from_summary(summary: dict[str, Any]) -> str:
    failed = int(summary.get("failed_outputs") or 0)
    warnings = int(summary.get("warnings_count") or 0)
    if failed:
        return "success_with_warnings" if failed < int(summary.get("total_videos") or 0) else "failed"
    return "success_with_warnings" if warnings else "success"


def _finalize(result: dict[str, Any], started: float) -> dict[str, Any]:
    result["runtime_seconds"] = round(perf_counter() - started, 3)
    if result["errors"] and result["status"] == "success":
        result["status"] = "success_with_warnings"
    return result


def _resolve_config_path(path: Path) -> Path:
    path = path.expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy config E2E: {path}")
    return path


def _resolve_path(value: str | Path, base_dir: Path, *, must_exist: bool) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    if must_exist and not path.exists():
        raise FileNotFoundError(f"Không tìm thấy path: {path}")
    return path


def _friendly_error(exc: Exception) -> str:
    text = " ".join(str(exc).split())
    lowered = text.lower()
    if "faster-whisper" in lowered or "faster_whisper" in lowered:
        return "Không tìm thấy faster-whisper. Hãy cài dependency hoặc chạy với --skip-asr."
    if "gemini" in lowered:
        return f"Gemini translation failed: {text}"
    return text or "E2E test failed without a detailed error."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Douyin Reup real batch E2E QA.")
    parser.add_argument("--config", required=True, help="Path to douyin reup E2E config JSON.")
    parser.add_argument("--scan-only", action="store_true")
    parser.add_argument("--translate-only", action="store_true")
    parser.add_argument("--review-mode", action="store_true")
    parser.add_argument("--render-approved", action="store_true")
    parser.add_argument("--auto-render", action="store_true")
    parser.add_argument("--skip-asr", action="store_true")
    parser.add_argument("--mock-translation", action="store_true")
    parser.add_argument("--debug", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_e2e(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"success", "success_with_warnings"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
