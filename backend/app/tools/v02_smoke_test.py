from __future__ import annotations

import argparse
import io
import json
import sys
import uuid
from pathlib import Path
from time import perf_counter
from typing import Any

from pydantic import ValidationError

from app import database
from app.adapters.ffmpeg_adapter import FFmpegError, run_ffmpeg
from app.modules.audio.audio_normalizer import normalize_audio_for_render
from app.modules.content_manager.content_service import ContentService
from app.modules.content_safety.safety_guard_service import SafetyGuardService
from app.modules.crop_safety.crop_safety_service import CropSafetyService
from app.modules.industry_presets.industry_preset_service import IndustryPresetService
from app.modules.media_scanner.scanner import MediaScanner
from app.modules.output_review.review_service import OutputQualityReviewService
from app.modules.product_import import ProductImportService, RawProductInput, to_project_product_info
from app.modules.renderer.overlay_renderer import OverlayRenderer
from app.modules.render_worker.render_worker import render_project
from app.modules.script_variants.script_variant_generator import ScriptVariantGenerator
from app.modules.segment_scoring.segment_scorer import SegmentScorer
from app.modules.segmenter.segmenter import Segmenter
from app.modules.source_media_manager.media_manager_service import build_source_media_items_from_data
from app.modules.subtitle_generator.subtitle_generator import SubtitleGenerator
from app.modules.timeline_templates.product_timeline_builder import ProductTimelineBuilder
from app.modules.visual_style.overlay_asset_builder import build_overlay_asset
from app.modules.visual_style.subtitle_style_renderer import generate_ass_subtitle
from app.modules.visual_style.visual_style_service import VisualStyleService, parse_resolution
from app.modules.voice_generator.voice_generator import VoiceGenerator
from app.schemas.project_schema import ProjectConfig
from app.utils.dependency_manager import ensure_runtime_dependencies
from app.utils.file_utils import ensure_dir


if sys.stdout.encoding and sys.stdout.encoding.lower() not in {"utf-8", "utf8"}:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}


def run_v02_smoke_test(
    config_path: Path,
    *,
    preview_only: bool = True,
    skip_tts_online: bool = False,
    clear_cache: bool = False,
    debug: bool = False,
) -> dict[str, Any]:
    started = perf_counter()
    config_path = config_path.expanduser()
    if not config_path.is_absolute():
        config_path = (Path.cwd() / config_path).resolve()

    result: dict[str, Any] = {
        "status": "success",
        "project_name": None,
        "mode": "preview" if preview_only else "full",
        "steps": {},
        "output_folder": None,
        "preview_path": None,
        "outputs": [],
        "performance_baseline": _empty_performance_baseline(),
        "warnings": [],
        "errors": [],
    }
    timings: dict[str, float] = {}
    original_db_path = database.DB_PATH

    try:
        _check_environment(result)
        raw_config = _load_raw_config(config_path)
        _step(result, "load_config", "ok")

        raw_config = _apply_product_input(config_path, raw_config, result)
        config = _build_config(raw_config)
        _step(result, "product_import", "ok")

        config = _apply_industry_preset(config, result)
        config = _apply_runtime_flags(config, skip_tts_online=skip_tts_online, clear_cache=clear_cache)
        output_dir = ensure_dir(_resolve_path(config.output_folder, config_path.parent, must_exist=False))
        config = config.model_copy(update={"output_folder": str(output_dir)})
        source_dir, used_synthetic = _prepare_source_media(config, config_path.parent, output_dir, result)
        config = config.model_copy(update={"source_folder": str(source_dir)})
        if used_synthetic:
            config = _synthetic_runtime_config(config, full=not preview_only)

        result["project_name"] = config.project_name
        result["output_folder"] = str(output_dir)
        project_id = f"v02-{uuid.uuid4().hex[:12]}"
        job_id = f"{project_id}-job"
        database.DB_PATH = output_dir / "v02_smoke.db"
        database.init_db()
        database.create_project(project_id, config.model_dump(mode="json"))

        preflight = _run_preflight(project_id, config, output_dir / "_v02_preflight", result, timings)
        _render_and_postprocess(
            project_id=project_id,
            job_id=job_id,
            config=config,
            preview_only=preview_only,
            result=result,
            timings=timings,
            preflight=preflight,
        )

    except Exception as exc:
        if debug:
            raise
        _error(result, _friendly_error(exc))
    finally:
        database.DB_PATH = original_db_path

    result["performance_baseline"] = _build_performance_baseline(result, timings, perf_counter() - started)
    if result["errors"]:
        result["status"] = "failed"
    elif result["warnings"] or any(value in {"warning", "skip"} for value in result["steps"].values()):
        result["status"] = "success_with_warnings"
    else:
        result["status"] = "success"
    return result


def _check_environment(result: dict[str, Any]) -> None:
    issues: list[str] = []
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 11):
        issues.append(f"Python >= 3.11 required, found {major}.{minor}")
    dependency_report = ensure_runtime_dependencies(auto_install=False)
    if not dependency_report.ffmpeg_path:
        issues.append("FFmpeg is not available. Install FFmpeg or set AUTO_TOOL_FFMPEG_DIR.")
    if not dependency_report.ffprobe_path:
        issues.append("ffprobe is not available. Install FFmpeg or set AUTO_TOOL_FFMPEG_DIR.")
    if issues:
        result["steps"]["environment"] = "failed"
        raise RuntimeError("; ".join(issues))
    _step(result, "environment", "ok")


def _load_raw_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"Config file does not exist: {config_path}")
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Config JSON is invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Config JSON must be an object.")
    return payload


def _apply_product_input(config_path: Path, raw_config: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    product_input = config_path.parent.parent / "product_inputs" / f"{config_path.stem}.txt"
    if not product_input.exists():
        _warn(result, f"product_input_missing: {product_input}")
        return raw_config

    product_text = product_input.read_text(encoding="utf-8")
    imported = ProductImportService().import_product_info(
        RawProductInput(
            input_type="txt",
            file_path=str(product_input),
            file_content=product_text,
            source_name=product_input.name,
        )
    )
    if not imported.success or imported.product is None:
        messages = "; ".join(issue.message for issue in imported.issues) or "unknown import error"
        _warn(result, f"product_import_warning: {messages}")
        return raw_config

    updated = dict(raw_config)
    updated["product"] = to_project_product_info(imported.product).model_dump(mode="json")
    if not (updated.get("industry") or {}).get("preset_id") and imported.product.industry_preset_id:
        updated["industry"] = {"preset_id": imported.product.industry_preset_id}
    _warn_for_issues(result, "product_import", imported.issues)
    return updated


def _build_config(raw_config: dict[str, Any]) -> ProjectConfig:
    try:
        return ProjectConfig.model_validate(raw_config)
    except ValidationError as exc:
        lines = ["Invalid project config:"]
        for item in exc.errors():
            location = ".".join(str(part) for part in item.get("loc", [])) or "config"
            lines.append(f"- {location}: {item.get('msg', 'validation error')}")
        raise ValueError("\n".join(lines)) from exc


def _apply_industry_preset(config: ProjectConfig, result: dict[str, Any]) -> ProjectConfig:
    preset_id = config.industry.preset_id if config.industry else None
    if not preset_id:
        _step(result, "industry_preset", "skip", "No industry preset configured.")
        return config
    updated = IndustryPresetService().apply_preset_to_config(
        config,
        preset_id,
        apply_visual_style=True,
        apply_timeline=True,
        apply_script_variation=True,
        apply_tts_voice=True,
        apply_edit_strength=False,
    )
    _step(result, "industry_preset", "ok")
    return updated


def _apply_runtime_flags(
    config: ProjectConfig,
    *,
    skip_tts_online: bool,
    clear_cache: bool,
) -> ProjectConfig:
    updates: dict[str, Any] = {}
    if skip_tts_online:
        updates["tts"] = config.tts.model_copy(
            update={
                "provider": "silent",
                "fallback_provider": "silent",
                "voice": "silent",
                "output_format": "wav",
            }
        )
    if clear_cache:
        updates["cache"] = config.cache.model_copy(update={"clear_cache_before_render": True})
    return config.model_copy(update=updates) if updates else config


def _prepare_source_media(
    config: ProjectConfig,
    base_dir: Path,
    output_dir: Path,
    result: dict[str, Any],
) -> tuple[Path, bool]:
    source_dir = _resolve_path(config.source_folder, base_dir, must_exist=False)
    source_videos = _list_video_files(source_dir) if source_dir.exists() else []
    if source_videos:
        return source_dir, False

    synthetic_dir = ensure_dir(output_dir / "_synthetic_source")
    _create_synthetic_videos(synthetic_dir, count=max(3, config.render.output_count), duration=8.0)
    _warn(
        result,
        "source_videos_missing_synthetic_fallback: No real source videos found, using generated test videos.",
    )
    return synthetic_dir, True


def _synthetic_runtime_config(config: ProjectConfig, *, full: bool) -> ProjectConfig:
    render = config.render.model_copy(
        update={
            "duration": min(config.render.duration, 6.0),
            "resolution": "360x640",
            "fps": min(config.render.fps, 15),
            "output_count": config.render.output_count if full else min(config.render.output_count, 3),
        }
    )
    effects = config.effects.model_copy(update={"subtitle_size": min(config.effects.subtitle_size, 36)})
    return config.model_copy(update={"render": render, "effects": effects})


def _run_preflight(
    project_id: str,
    config: ProjectConfig,
    preflight_dir: Path,
    result: dict[str, Any],
    timings: dict[str, float],
) -> dict[str, Any]:
    ensure_dir(preflight_dir)
    preflight: dict[str, Any] = {}

    media = _timed(timings, "scan_seconds", lambda: MediaScanner().scan_folder(config.source_folder))
    if not media:
        raise ValueError(f"No valid videos found in {config.source_folder}")
    preflight["media"] = media
    _step(result, "scan", "ok")

    segments = _timed(timings, "segment_seconds", lambda: Segmenter().create_segments(media, config.effects.cut_intensity))
    if not segments:
        raise ValueError("No segments could be created from source videos.")
    preflight["segments"] = segments
    _step(result, "segments", "ok")

    scored = _timed(timings, "segment_scoring_seconds", lambda: SegmentScorer().score_segments(segments))
    preflight["scored_segments"] = scored
    _step(result, "segment_scoring", "ok")

    source_items = build_source_media_items_from_data(project_id, config, media, scored)
    preflight["source_media_items"] = source_items
    _step(result, "source_media", "ok")

    usable = [item for item in scored if item.score_detail is not None and not item.score_detail.is_rejected] or scored
    timelines = ProductTimelineBuilder().build_timelines(
        segments=usable,
        output_count=1,
        target_duration=config.render.duration,
        template_id=config.timeline.template_id,
        speed_variation=config.effects.speed_variation,
    )
    if not timelines:
        raise ValueError("Could not build a product-aware timeline.")
    preflight["timeline"] = timelines[0]
    _step(result, "timeline", "ok")

    crop_report = _timed(
        timings,
        "crop_safety_seconds",
        lambda: CropSafetyService().analyze_timelines(timelines, config, preflight_dir, project_id=project_id),
    )
    preflight["crop_report"] = crop_report
    _step(result, "crop_safety", "ok")

    script_generator = ScriptVariantGenerator()
    scripts = _timed(
        timings,
        "script_seconds",
        lambda: script_generator.generate_variants(config, output_count=1, timeline_template_id=config.timeline.template_id),
    )
    if not scripts:
        raise ValueError("No script variants were generated.")
    preflight["script"] = scripts[0]
    _step(result, "script_variants", "ok")

    safety = SafetyGuardService().check_script_output(scripts[0], config.product, target_duration=config.render.duration)
    if safety.errors_count:
        _warn(result, "script_safety_preflight_warning: generated script required fallback during render.")
        _step(result, "script_safety", "warning")
    else:
        _step(result, "script_safety", "ok")

    voice_generator = VoiceGenerator()
    voice_path = _timed(
        timings,
        "tts_seconds",
        lambda: voice_generator.generate_voiceover(
            scripts[0],
            str(preflight_dir),
            filename="v02_preflight_voice.wav",
            text_filename="v02_preflight_voice_text.txt",
            language=config.ai.language,
            target_duration=config.render.duration,
            tts_settings=config.tts,
        ),
    )
    normalized_voice = normalize_audio_for_render(
        voice_path,
        str(preflight_dir / "v02_preflight_voice_normalized.wav"),
        target_format="wav",
        sample_rate=44100,
    )
    preflight["voice_path"] = normalized_voice
    _step(result, "tts", "ok")

    subtitle_generator = SubtitleGenerator()
    subtitle_path = preflight_dir / "v02_preflight_sub.srt"
    subtitle_generator.generate_srt(
        scripts[0],
        target_video_duration=config.render.duration,
        voice_duration=config.render.duration,
        output_path=str(subtitle_path),
        subtitle_lines=voice_generator.last_subtitle_timeline,
    )
    width, height = parse_resolution(config.render.resolution)
    preset = VisualStyleService().resolve_preset(config.visual_style)
    ass_path = preflight_dir / "v02_preflight_sub.ass"
    generate_ass_subtitle(
        voice_generator.last_subtitle_timeline or scripts[0].subtitles,
        preset,
        video_width=width,
        video_height=height,
        output_path=str(ass_path),
    )
    overlay_path = preflight_dir / "v02_preflight_overlay.png"
    build_overlay_asset(preset, width, height, str(overlay_path))
    if not subtitle_path.exists() or not ass_path.exists() or not overlay_path.exists():
        raise ValueError("Subtitle/overlay preflight did not create expected assets.")
    _step(result, "subtitle_overlay", "ok")

    return preflight


def _render_and_postprocess(
    *,
    project_id: str,
    job_id: str,
    config: ProjectConfig,
    preview_only: bool,
    result: dict[str, Any],
    timings: dict[str, float],
    preflight: dict[str, Any],
) -> None:
    database.create_job(job_id, project_id, preview_only=preview_only, total_outputs=1 if preview_only else config.render.output_count)
    logs: list[dict[str, str]] = []

    def log_callback(level: str, message: str) -> None:
        logs.append({"level": level, "message": message})
        database.add_job_log(job_id, level, message)

    summary = _timed(
        timings,
        "render_total_seconds",
        lambda: render_project(
            config,
            preview_only=preview_only,
            project_id=project_id,
            log_callback=log_callback,
        ),
    )
    result["output_folder"] = summary.get("output_folder")
    result["outputs"] = summary.get("outputs", [])
    output_folder = Path(str(summary.get("output_folder") or config.output_folder))
    outputs = [item for item in summary.get("outputs", []) if isinstance(item, dict)]
    preview_path = _first_output_path(outputs)
    result["preview_path"] = preview_path

    database.update_job(
        job_id,
        status="completed" if int(summary.get("failed_outputs") or 0) == 0 else "completed_with_errors",
        current_step="completed",
        progress=100,
        total_outputs=int(summary.get("requested_outputs") or len(outputs) or 0),
        completed_outputs=int(summary.get("successful_outputs") or 0),
        failed_outputs=int(summary.get("failed_outputs") or 0),
        output_folder=str(output_folder),
        results_json=json.dumps({"outputs": outputs, "cache_summary": summary.get("cache_summary")}, ensure_ascii=False),
        error=summary.get("error"),
    )

    _validate_render_outputs(preview_only, output_folder, outputs, result)
    if int(summary.get("failed_outputs") or 0) > 0:
        _warn(result, f"render_completed_with_failed_outputs: {summary.get('failed_outputs')}")
        _step(result, "preview_render" if preview_only else "full_render", "warning")
    else:
        _step(result, "preview_render" if preview_only else "full_render", "ok")

    if preview_path and Path(preview_path).exists():
        _step(result, "qa", "ok")
    else:
        _step(result, "qa", "failed", "Rendered output file was not created.")
        _error(result, "Rendered output file was not created.")

    if not preview_only:
        scores = OutputQualityReviewService().analyze_project_outputs(project_id)
        if not (output_folder / "output_quality_review.json").exists():
            raise ValueError("output_quality_review.json was not created.")
        result["output_quality_review_count"] = len(scores)
        _step(result, "output_quality_review", "ok")
    else:
        _step(result, "output_quality_review", "skip", "Preview-only run.")

    content_items = ContentService().get_content_items(project_id)
    export_files = ContentService().export_content(project_id, ["json", "csv", "txt", "md"])
    result["content_items_count"] = len(content_items)
    result["content_export_files"] = export_files
    if not Path(export_files.get("md", "")).exists():
        raise ValueError("content_plan.md was not created.")
    _step(result, "content_export", "ok")

    _merge_output_performance(result, timings, outputs)


def _validate_render_outputs(
    preview_only: bool,
    output_folder: Path,
    outputs: list[dict[str, Any]],
    result: dict[str, Any],
) -> None:
    required_common = [
        "segment_scoring_report.json",
        "crop_safety_report.json",
        "script_variants.json",
        "project_summary.json",
    ]
    for filename in required_common:
        if not (output_folder / filename).exists():
            _warn(result, f"missing_expected_output: {filename}")

    expected_count = 1 if preview_only else 3
    if not preview_only and len(outputs) != expected_count:
        _warn(result, f"full_output_count_mismatch: expected 3, got {len(outputs)}")

    prefixes = ["preview_001"] if preview_only else [f"video_{index:03d}" for index in range(1, 4)]
    for prefix in prefixes:
        for suffix in [".mp4", "_script.json", "_sub.srt", "_sub.ass", "_timeline.json", "_log.json"]:
            if not (output_folder / f"{prefix}{suffix}").exists():
                _warn(result, f"missing_expected_output: {prefix}{suffix}")
        voice_candidates = list(output_folder.glob(f"{prefix}_voice.*"))
        if not voice_candidates:
            _warn(result, f"missing_expected_output: {prefix}_voice.*")


def _create_synthetic_videos(source_dir: Path, *, count: int, duration: float) -> None:
    for index in range(1, count + 1):
        output_path = source_dir / f"synthetic_source_{index:03d}.mp4"
        if output_path.exists() and output_path.stat().st_size > 0:
            continue
        run_ffmpeg(
            [
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"testsrc2=size=360x640:rate=15:duration={duration:.3f}",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={440 + index * 80}:duration={duration:.3f}",
                "-shortest",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "28",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "64k",
                str(output_path),
            ]
        )


def _merge_output_performance(result: dict[str, Any], timings: dict[str, float], outputs: list[dict[str, Any]]) -> None:
    render_visual = 0.0
    render_final = 0.0
    script = 0.0
    tts = 0.0
    for output in outputs:
        performance = output.get("performance")
        if not isinstance(performance, dict):
            continue
        render_visual += float(performance.get("render_visual_seconds") or 0.0)
        render_final += float(performance.get("render_final_seconds") or 0.0)
        script += float(performance.get("script_seconds") or 0.0)
        tts += float(performance.get("tts_seconds") or 0.0)
    if render_visual or render_final:
        timings["render_preview_seconds"] = round(render_visual + render_final, 3)
    if script:
        timings["script_seconds"] = round(max(float(timings.get("script_seconds") or 0.0), script), 3)
    if tts:
        timings["tts_seconds"] = round(max(float(timings.get("tts_seconds") or 0.0), tts), 3)


def _build_performance_baseline(
    result: dict[str, Any],
    timings: dict[str, float],
    total_seconds: float,
) -> dict[str, float | None]:
    return {
        "scan_seconds": _rounded(timings.get("scan_seconds")),
        "segment_scoring_seconds": _rounded(timings.get("segment_scoring_seconds")),
        "crop_safety_seconds": _rounded(timings.get("crop_safety_seconds")),
        "script_seconds": _rounded(timings.get("script_seconds")),
        "tts_seconds": _rounded(timings.get("tts_seconds")),
        "render_preview_seconds": _rounded(timings.get("render_preview_seconds") or timings.get("render_total_seconds")),
        "total_preview_seconds": round(max(0.0, total_seconds), 3),
    }


def _empty_performance_baseline() -> dict[str, None]:
    return {
        "scan_seconds": None,
        "segment_scoring_seconds": None,
        "crop_safety_seconds": None,
        "script_seconds": None,
        "tts_seconds": None,
        "render_preview_seconds": None,
        "total_preview_seconds": None,
    }


def _resolve_path(path_value: str, base_dir: Path, *, must_exist: bool) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    if must_exist and not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    return path


def _list_video_files(source_dir: Path) -> list[Path]:
    if not source_dir.exists() or not source_dir.is_dir():
        return []
    return [
        path
        for path in source_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS and path.stat().st_size > 0
    ]


def _timed(timings: dict[str, float], key: str, action):
    start = perf_counter()
    try:
        return action()
    finally:
        timings[key] = round(max(0.0, perf_counter() - start), 3)


def _step(result: dict[str, Any], key: str, status: str, message: str | None = None) -> None:
    result["steps"][key] = status
    if message and status == "failed":
        _error(result, message)
    elif message and status in {"warning", "skip"}:
        _warn(result, f"{key}: {message}")


def _warn(result: dict[str, Any], message: str) -> None:
    warnings = result.setdefault("warnings", [])
    if message and message not in warnings:
        warnings.append(message)


def _error(result: dict[str, Any], message: str) -> None:
    errors = result.setdefault("errors", [])
    if message and message not in errors:
        errors.append(message)


def _warn_for_issues(result: dict[str, Any], prefix: str, issues: list[Any]) -> None:
    for issue in issues:
        severity = getattr(issue, "severity", None)
        if severity == "warning":
            _warn(result, f"{prefix}: {getattr(issue, 'message', issue)}")


def _first_output_path(outputs: list[dict[str, Any]]) -> str | None:
    for output in outputs:
        path = output.get("path")
        if path:
            return str(path)
    return None


def _rounded(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


def _friendly_error(exc: Exception) -> str:
    message = " ".join(str(exc).split())
    lower = message.lower()
    if isinstance(exc, FFmpegError) or "ffmpeg" in lower or "ffprobe" in lower:
        return f"FFmpeg/ffprobe error: {message[:500]}"
    if "permission" in lower or "access is denied" in lower:
        return f"Permission error: {message[:500]}"
    if "validation" in lower or "invalid project config" in lower:
        return message[:1000]
    return message[:700]


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto Tool v0.2 release-candidate smoke test")
    parser.add_argument("--config", required=True, type=Path, help="Path to a v0.2 product test config JSON.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preview-only", action="store_true", help="Render only one preview output.")
    mode.add_argument("--full", action="store_true", help="Render the full configured batch.")
    parser.add_argument("--skip-tts-online", action="store_true", help="Use silent offline TTS fallback.")
    parser.add_argument("--clear-cache", action="store_true", help="Clear project cache before render.")
    parser.add_argument("--debug", action="store_true", help="Raise raw exceptions for debugging.")
    args = parser.parse_args()

    result = run_v02_smoke_test(
        args.config,
        preview_only=not args.full,
        skip_tts_online=args.skip_tts_online,
        clear_cache=args.clear_cache,
        debug=args.debug,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] == "failed":
        sys.exit(1)


if __name__ == "__main__":
    main()
