from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.adapters.ffmpeg_adapter import probe_video
from app.modules.cache.cache_service import CacheService
from app.modules.crop_safety.crop_schema import CropSafetyClipReport, CropSafetyReport
from app.modules.crop_safety.crop_strategy import CropStrategyService, build_center_crop_box
from app.modules.timeline_builder.timeline_builder import Timeline, TimelineClip
from app.schemas.media_schema import MediaFile, VideoSegment
from app.schemas.project_schema import ProjectConfig
from app.utils.file_utils import write_json


class CropSafetyService:
    def __init__(
        self,
        strategy_service: CropStrategyService | None = None,
        cache_service: CacheService | None = None,
        cache_enabled: bool = True,
    ) -> None:
        self.strategy_service = strategy_service or CropStrategyService()
        self.cache_service = cache_service
        self.cache_enabled = cache_enabled
        self._media_cache: dict[str, MediaFile] = {}

    def analyze_timelines(
        self,
        timelines: list[Timeline],
        config: ProjectConfig,
        output_dir: Path,
        project_id: str | None = None,
    ) -> CropSafetyReport:
        clip_reports: list[CropSafetyClipReport] = []
        for timeline in timelines:
            updated_clips: list[TimelineClip] = []
            for clip_index, clip in enumerate(timeline.clips, start=1):
                result = self._analyze_clip(clip, config)
                updated_clips.append(
                    clip.model_copy(
                        update={
                            "crop_box": result.recommended_crop,
                            "crop_mode": result.crop_mode,
                            "crop_safety_score": result.overall_safety_score,
                            "crop_warnings": list(result.warnings),
                            "effective_zoom_motion": result.effective_zoom_motion,
                            "crop_cache_hit": result.cache_hit,
                        }
                    )
                )
                clip_reports.append(
                    CropSafetyClipReport(
                        output_index=timeline.output_index,
                        clip_index=clip_index,
                        source_path=clip.source_path,
                        start=clip.start,
                        end=clip.end,
                        crop_mode=result.crop_mode,
                        visibility_score=result.visibility_score,
                        overlay_risk_score=result.overlay_risk_score,
                        edge_risk_score=result.edge_risk_score,
                        zoom_risk_score=result.zoom_risk_score,
                        overall_safety_score=result.overall_safety_score,
                        warnings=list(result.warnings),
                        fallback_used=result.fallback_used,
                        cache_hit=result.cache_hit,
                    )
                )
            timeline.clips = updated_clips

        report = build_crop_safety_report(clip_reports, project_id=project_id)
        write_json(output_dir / "crop_safety_report.json", report.model_dump(mode="json"))
        return report

    def _analyze_clip(self, clip: TimelineClip, config: ProjectConfig):
        try:
            media = self._media_cache.get(clip.source_path)
            if media is None:
                media = probe_video(clip.source_path)
                self._media_cache[clip.source_path] = media
            segment = VideoSegment(
                source_path=clip.source_path,
                start=clip.start,
                end=clip.end,
                duration=max(0.05, clip.end - clip.start),
                score=max(0.0, min(1.0, clip.segment_score if clip.segment_score is not None else 0.7)),
            )
            cache_key = self._cache_key(clip, config)
            if cache_key:
                cached = self.cache_service.get_json("crop_safety", cache_key)
                if cached:
                    try:
                        from app.modules.crop_safety.crop_schema import CropAnalysisResult

                        return CropAnalysisResult.model_validate(cached).model_copy(update={"cache_hit": True})
                    except ValidationError:
                        pass

            result = self.strategy_service.choose_crop_strategy(media, segment, config)
            if cache_key:
                self.cache_service.set_json(
                    cache_key,
                    result.model_copy(update={"cache_hit": False}).model_dump(mode="json"),
                )
            return result
        except Exception as exc:
            width, height = _parse_resolution(config.render.resolution)
            media = self._media_cache.get(clip.source_path)
            input_width = media.width if media else width
            input_height = media.height if media else height
            from app.modules.crop_safety.crop_schema import CropAnalysisResult

            return CropAnalysisResult(
                source_path=clip.source_path,
                start=clip.start,
                end=clip.end,
                input_width=input_width,
                input_height=input_height,
                target_width=width,
                target_height=height,
                recommended_crop=build_center_crop_box(input_width, input_height, width, height),
                crop_mode="center_crop",
                visibility_score=0.5,
                overlay_risk_score=0.0,
                edge_risk_score=0.0,
                zoom_risk_score=0.0,
                overall_safety_score=0.5,
                warnings=[f"crop_analysis_failed_fallback_center_crop: {exc}"],
                fallback_used=True,
                effective_zoom_motion=config.effects.zoom_motion,
            )

    def _cache_key(self, clip: TimelineClip, config: ProjectConfig) -> str | None:
        if not self.cache_service or not self.cache_service.enabled or not self.cache_enabled:
            return None
        width, height = _parse_resolution(config.render.resolution)
        overlay_ratio = max(0.0, min(0.6, config.effects.overlay_height / 100))
        return self.cache_service.keys.build_crop_safety_key(
            clip.source_path,
            clip.start,
            clip.end,
            f"{width}x{height}",
            overlay_ratio,
            zoom_motion=config.effects.zoom_motion,
            crop_mode=config.crop_safety.mode,
        )


def build_crop_safety_report(clips: list[CropSafetyClipReport], project_id: str | None = None) -> CropSafetyReport:
    total = len(clips)
    average = round(sum(clip.overall_safety_score for clip in clips) / total, 3) if total else 0.0
    warnings = Counter(warning for clip in clips for warning in clip.warnings)
    return CropSafetyReport(
        project_id=project_id,
        total_clips_analyzed=total,
        average_crop_safety_score=average,
        fallback_to_blur_background=sum(1 for clip in clips if clip.crop_mode == "safe_fit_blur_background"),
        center_crop_used=sum(1 for clip in clips if clip.crop_mode in {"center_crop", "smart_center"}),
        warnings_summary=dict(warnings),
        clips=clips,
    )


def summarize_crop_safety_for_output(timeline: Timeline) -> dict[str, Any]:
    clips = timeline.clips
    scores = [clip.crop_safety_score for clip in clips if clip.crop_safety_score is not None]
    warnings = [
        f"clip_{index}: {warning}"
        for index, clip in enumerate(clips, start=1)
        for warning in clip.crop_warnings
    ]
    return {
        "average_score": round(sum(scores) / len(scores), 3) if scores else None,
        "fallback_to_blur_background": sum(1 for clip in clips if clip.crop_mode == "safe_fit_blur_background"),
        "cache_hits": sum(1 for clip in clips if clip.crop_cache_hit),
        "warnings": warnings,
    }


def _parse_resolution(value: str) -> tuple[int, int]:
    width, height = value.lower().split("x")
    return int(width), int(height)
