from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from app import database
from app.modules.cache.cache_service import CacheService
from app.modules.crop_safety.crop_safety_service import CropSafetyService
from app.modules.media_scanner.scanner import MediaScanner
from app.modules.music_selector.music_selector import MusicSelector
from app.modules.output_review.review_schema import OutputReviewStatus
from app.modules.output_review.review_service import (
    OutputQualityReviewService,
    latest_outputs_for_project,
)
from app.modules.render_worker.output_pipeline import render_one_output
from app.modules.render_worker.summary_builder import finalize_summary
from app.modules.renderer.renderer import Renderer
from app.modules.segment_scoring.segment_scorer import SegmentScorer, build_scoring_report
from app.modules.segmenter.segmenter import Segmenter
from app.modules.source_media_manager.media_filter_service import MediaFilterService, summarize_timeline_source_filter
from app.modules.script_writer.script_writer import ProductVideoScript
from app.modules.subtitle_generator.subtitle_generator import SubtitleGenerator
from app.modules.timeline_builder.timeline_builder import Timeline
from app.modules.timeline_templates.product_timeline_builder import ProductTimelineBuilder
from app.modules.voice_generator.voice_generator import VoiceGenerator
from app.schemas.media_schema import VideoSegment
from app.schemas.project_schema import ProjectConfig
from app.utils.file_utils import ensure_dir, write_json


ProgressCallback = Callable[[dict[str, Any]], None]
LogCallback = Callable[[str, str], None]


class RerenderService:
    def resolve_output_indexes(
        self,
        project_id: str,
        mode: str,
        output_indexes: list[int] | None = None,
    ) -> list[int]:
        mode = mode.strip().lower()
        latest_outputs = latest_outputs_for_project(project_id)
        if not latest_outputs:
            raise ValueError("No render outputs were found for this project.")

        if mode == "selected":
            requested = sorted({int(index) for index in (output_indexes or []) if int(index) > 0})
            if not requested:
                raise ValueError("output_indexes is required when mode is selected.")
            missing = [index for index in requested if index not in latest_outputs]
            if missing:
                raise ValueError(f"Output indexes not found: {missing}")
            return requested

        scores = OutputQualityReviewService().analyze_project_outputs(project_id)
        reviews = {item["output_index"]: item for item in database.list_output_reviews(project_id)}

        if mode == "failed_only":
            selected = [score.output_index for score in scores if score.recommended_action == "rerender_failed"]
        elif mode == "needs_rerender":
            selected = [
                score.output_index
                for score in scores
                if score.recommended_action == "needs_rerender"
                or reviews.get(score.output_index, {}).get("review_status") == OutputReviewStatus.needs_rerender.value
            ]
        elif mode == "bad_and_failed":
            selected = [
                score.output_index
                for score in scores
                if score.recommended_action in {"bad", "rerender_failed"}
                or reviews.get(score.output_index, {}).get("review_status") == OutputReviewStatus.bad.value
            ]
        else:
            raise ValueError(f"Unsupported rerender mode: {mode}")

        return sorted(set(selected))

    def rerender_outputs(
        self,
        project_id: str,
        config: ProjectConfig,
        output_indexes: list[int],
        mode: str,
        reuse_script: bool = True,
        reuse_timeline: bool = False,
        reuse_settings: bool = True,
        progress_callback: ProgressCallback | None = None,
        log_callback: LogCallback | None = None,
    ) -> dict[str, Any]:
        if not output_indexes:
            raise ValueError("No outputs were selected for rerender.")

        created_at = datetime.now().replace(microsecond=0)
        output_dir = _next_rerender_dir(config.output_folder)
        cache_service = CacheService.for_project(config, log_callback=log_callback)
        if config.cache.clear_cache_before_render:
            cache_service.clear()
            _log(log_callback, "info", "Đã xoá cache dự án trước khi render lại.")
        latest_outputs = latest_outputs_for_project(project_id)
        outputs: list[dict[str, Any]] = []
        summary: dict[str, Any] = {
            "project_id": project_id,
            "project_name": config.project_name,
            "created_at": created_at.isoformat(),
            "output_folder": str(output_dir),
            "requested_outputs": len(output_indexes),
            "requested_output_indexes": output_indexes,
            "total_outputs": len(output_indexes),
            "successful_outputs": 0,
            "failed_outputs": 0,
            "warnings_count": 0,
            "failed_items": [],
            "reuse_script": reuse_script,
            "reuse_timeline": reuse_timeline,
            "reuse_settings": reuse_settings,
            "mode": mode,
            "cache_summary": cache_service.summary(),
            "outputs": outputs,
        }

        _log(log_callback, "info", f"Rerender output indexes: {output_indexes}")
        _log(log_callback, "info", f"Rerender output folder: {output_dir}")
        _progress(
            progress_callback,
            current_step="preparing_rerender",
            progress=5,
            total_outputs=len(output_indexes),
            completed_outputs=0,
            failed_outputs=0,
        )

        new_timelines = self._build_new_timelines_if_needed(
            config=config,
            project_id=project_id,
            output_indexes=output_indexes,
            latest_outputs=latest_outputs,
            reuse_timeline=reuse_timeline,
            output_dir=output_dir,
            cache_service=cache_service,
            log_callback=log_callback,
            progress_callback=progress_callback,
        )

        renderer = Renderer()
        voice_generator = VoiceGenerator(
            cache_service=cache_service,
            cache_enabled=config.cache.cache_tts,
        )
        subtitle_generator = SubtitleGenerator()
        music_selector = MusicSelector()
        crop_safety_service = CropSafetyService(
            cache_service=cache_service,
            cache_enabled=config.cache.cache_crop_safety,
        )

        for position, index in enumerate(output_indexes, start=1):
            completed = sum(1 for item in outputs if item["status"] in {"success", "warning"})
            failed = sum(1 for item in outputs if item["status"] == "failed")
            _progress(
                progress_callback,
                current_step=f"rerendering_video_{index}",
                progress=20 + int(((position - 1) / max(1, len(output_indexes))) * 75),
                total_outputs=len(output_indexes),
                completed_outputs=completed,
                failed_outputs=failed,
            )
            _log(log_callback, "info", f"Rerender output {index}")
            _log(log_callback, "info", f"Reuse script: {reuse_script}")
            _log(log_callback, "info", f"Reuse timeline: {reuse_timeline}")

            previous_output = latest_outputs.get(index, {})
            timeline = self._timeline_for_output(
                index=index,
                previous_output=previous_output,
                reuse_timeline=reuse_timeline,
                new_timelines=new_timelines,
                log_callback=log_callback,
            )
            script_override = self._script_for_output(previous_output, reuse_script, log_callback)
            crop_safety_service.analyze_timelines(
                timelines=[timeline],
                config=config,
                output_dir=output_dir,
                project_id=project_id,
            )
            outputs.append(
                render_one_output(
                    index=index,
                    timeline=timeline,
                    config=config,
                    output_dir=output_dir,
                    renderer=renderer,
                    voice_generator=voice_generator,
                    subtitle_generator=subtitle_generator,
                    music_selector=music_selector,
                    custom_script=None,
                    script_override=script_override,
                    preview_only=False,
                    log_callback=log_callback,
                    cache_service=cache_service,
                    source_media_filter_summary=summarize_timeline_source_filter(timeline),
                )
            )

        finalize_summary(summary)
        summary["cache_summary"] = cache_service.summary()
        successful_output_indexes = [item["index"] for item in outputs if item.get("status") in {"success", "warning"}]
        failed_output_indexes = [item["index"] for item in outputs if item.get("status") == "failed"]
        summary_path = output_dir / "rerender_summary.json"
        write_json(
            summary_path,
            {
                **summary,
                "requested_outputs": output_indexes,
                "successful_outputs": successful_output_indexes,
                "failed_outputs": failed_output_indexes,
                "cache_summary": summary.get("cache_summary"),
            },
        )
        _log(log_callback, "info", f"Rerender summary written: {summary_path}")

        try:
            OutputQualityReviewService().analyze_project_outputs(project_id)
        except Exception as exc:
            _log(log_callback, "warning", f"Could not refresh output quality review after rerender: {exc}")

        _progress(
            progress_callback,
            current_step="completed",
            progress=100,
            total_outputs=len(output_indexes),
            completed_outputs=int(summary["successful_outputs"]),
            failed_outputs=int(summary["failed_outputs"]),
        )
        return {
            "project_id": project_id,
            "project_name": config.project_name,
            "created_at": created_at.isoformat(),
            "output_folder": str(output_dir),
            "requested_outputs": len(output_indexes),
            "successful_outputs": len(successful_output_indexes),
            "failed_outputs": len(failed_output_indexes),
            "outputs": outputs,
            "cache_summary": summary.get("cache_summary"),
            "rerender_summary": str(summary_path),
        }

    def _build_new_timelines_if_needed(
        self,
        config: ProjectConfig,
        project_id: str,
        output_indexes: list[int],
        latest_outputs: dict[int, dict[str, Any]],
        reuse_timeline: bool,
        output_dir: Path,
        cache_service: CacheService,
        log_callback: LogCallback | None,
        progress_callback: ProgressCallback | None,
    ) -> dict[int, Timeline]:
        missing_new_timeline = [
            index
            for index in output_indexes
            if not reuse_timeline or not _load_timeline(latest_outputs.get(index, {}).get("timeline_file"))
        ]
        if not missing_new_timeline:
            return {}

        _progress(
            progress_callback,
            current_step="building_rerender_timelines",
            progress=12,
            total_outputs=len(output_indexes),
            completed_outputs=0,
            failed_outputs=0,
        )
        media_files = MediaScanner(
            cache_service=cache_service,
            cache_enabled=config.cache.cache_media_metadata,
        ).scan_folder(config.source_folder)
        if not media_files:
            raise ValueError(f"No valid input videos found in {config.source_folder}")
        segments = Segmenter().create_segments(media_files, config.effects.cut_intensity)
        if not segments:
            raise ValueError("No usable segments were created from the input videos.")
        scored_segments = SegmentScorer(
            cache_service=cache_service,
            cache_enabled=config.cache.cache_segment_scoring,
            settings_hash=cache_service.settings_hash(
                {
                    "scorer": "segment_scorer_v1",
                    "max_frames": 5,
                    "resolution": config.render.resolution,
                }
            ),
        ).score_segments(segments)
        scoring_report = build_scoring_report(scored_segments)
        write_json(output_dir / "segment_scoring_report.json", scoring_report)
        media_filter = MediaFilterService(log_callback=log_callback)
        filtered_segments = media_filter.filter_segments_for_render(project_id, scored_segments, config=config)
        timeline_segments = _select_timeline_segments(filtered_segments, len(output_indexes))
        built = ProductTimelineBuilder().build_timelines(
            segments=timeline_segments,
            output_count=max(output_indexes),
            target_duration=config.render.duration,
            template_id=config.timeline.template_id,
            speed_variation=config.effects.speed_variation,
        )
        _log(log_callback, "info", "Build new timeline: success")
        return {timeline.output_index: timeline for timeline in built if timeline.output_index in output_indexes}

    def _timeline_for_output(
        self,
        index: int,
        previous_output: dict[str, Any],
        reuse_timeline: bool,
        new_timelines: dict[int, Timeline],
        log_callback: LogCallback | None,
    ) -> Timeline:
        if reuse_timeline:
            timeline = _load_timeline(previous_output.get("timeline_file"))
            if timeline is not None:
                _log(log_callback, "info", f"Reused timeline for output {index}")
                return timeline.model_copy(update={"output_index": index})
            _log(log_callback, "warning", f"Could not reuse timeline for output {index}; building a new one.")

        timeline = new_timelines.get(index)
        if timeline is None:
            raise ValueError(f"Could not build timeline for rerender output {index}")
        return timeline.model_copy(update={"output_index": index})

    def _script_for_output(
        self,
        previous_output: dict[str, Any],
        reuse_script: bool,
        log_callback: LogCallback | None,
    ) -> ProductVideoScript | None:
        if not reuse_script:
            return None
        script = _load_script(previous_output.get("script_file"))
        if script is None:
            _log(log_callback, "warning", "Could not reuse script; a new script will be generated.")
            return None
        _log(log_callback, "info", "Reuse script: success")
        return script


def _next_rerender_dir(output_folder: str) -> Path:
    root = ensure_dir(Path(output_folder) / "rerenders")
    existing = []
    for path in root.glob("run_*"):
        if not path.is_dir():
            continue
        try:
            existing.append(int(path.name.split("_", 1)[1]))
        except (IndexError, ValueError):
            continue
    return ensure_dir(root / f"run_{(max(existing) + 1 if existing else 1):03d}")


def _load_timeline(path_value: Any) -> Timeline | None:
    payload = _read_json(path_value)
    if not payload:
        return None
    try:
        return Timeline.model_validate(payload)
    except Exception:
        return None


def _load_script(path_value: Any) -> ProductVideoScript | None:
    payload = _read_json(path_value)
    if not payload:
        return None
    try:
        return ProductVideoScript.model_validate(payload)
    except Exception:
        return None


def _read_json(path_value: Any) -> dict[str, Any]:
    if not path_value:
        return {}
    try:
        path = Path(str(path_value))
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _select_timeline_segments(segments: list[VideoSegment], output_count: int) -> list[VideoSegment]:
    usable_segments = [
        segment
        for segment in segments
        if segment.score_detail is not None and not segment.score_detail.is_rejected
    ]
    favorite_segments = [
        segment
        for segment in segments
        if getattr(segment, "user_review_status", None) == "favorite"
    ]
    if favorite_segments:
        merged = {
            (segment.id, segment.source_path, segment.start, segment.end): segment
            for segment in [*favorite_segments, *usable_segments]
        }
        usable_segments = list(merged.values())
    if not usable_segments:
        raise ValueError("No usable video segments after scoring")
    minimum_segments = max(3, output_count)
    if len(usable_segments) >= minimum_segments:
        return usable_segments
    rejected = sorted(
        [segment for segment in segments if segment not in usable_segments],
        key=lambda segment: segment.score,
        reverse=True,
    )
    return (usable_segments + rejected)[: max(minimum_segments, len(usable_segments))]


def _progress(callback: ProgressCallback | None, **payload: Any) -> None:
    if callback:
        callback(payload)


def _log(callback: LogCallback | None, level: str, message: str) -> None:
    if callback:
        callback(level, message)
