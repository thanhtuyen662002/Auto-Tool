from __future__ import annotations

from app.adapters.ffmpeg_adapter import probe_video
from app.modules.crop_safety.crop_schema import CropAnalysisResult, CropBox
from app.modules.crop_safety.frame_saliency import FrameSaliencyAnalyzer
from app.modules.segment_scoring.frame_sampler import FrameSampler


class CropAnalyzer:
    def __init__(self, frame_sampler: FrameSampler | None = None, saliency_analyzer: FrameSaliencyAnalyzer | None = None) -> None:
        self.frame_sampler = frame_sampler or FrameSampler()
        self.saliency_analyzer = saliency_analyzer or FrameSaliencyAnalyzer()

    def analyze_video_or_segment(
        self,
        source_path: str,
        start: float | None,
        end: float | None,
        target_width: int,
        target_height: int,
        overlay_height_ratio: float,
        zoom_motion: int = 0,
    ) -> CropAnalysisResult:
        media = probe_video(source_path)
        safe_start = max(0.0, float(start or 0.0))
        safe_end = min(media.duration, float(end if end is not None else media.duration))
        crop = _base_crop_box(media.width, media.height, target_width, target_height)
        fallback = False
        warnings: list[str] = []

        try:
            frames = self.frame_sampler.sample_frames(source_path, safe_start, safe_end, max_frames=3)
            saliency = _average_saliency([self.saliency_analyzer.analyze_frame(frame) for frame in frames])
        except Exception as exc:
            saliency = _neutral_saliency()
            fallback = True
            warnings.append(f"crop_analysis_failed_fallback_center_crop: {exc}")

        crop = _crop_around_saliency(media.width, media.height, crop.width, crop.height, saliency["center_x"], saliency["center_y"])
        input_aspect = media.width / media.height
        target_aspect = target_width / target_height
        crop_loss_ratio = 1.0 - ((crop.width * crop.height) / max(1, media.width * media.height))
        edge_risk = max(float(saliency["left_edge_score"]), float(saliency["right_edge_score"]))
        overlay_risk = _overlay_risk(saliency, overlay_height_ratio)
        visibility = max(0.0, min(1.0, 1.0 - crop_loss_ratio * 0.85 - max(0, edge_risk - 0.38) * 0.55))
        zoom_risk = 0.0
        effective_zoom_motion = zoom_motion
        crop_mode = "smart_center"

        if abs(input_aspect - target_aspect) < 0.08:
            crop_mode = "no_crop_scale"
            crop = CropBox(x=0, y=0, width=media.width, height=media.height)
            visibility = 0.96
        elif input_aspect > target_aspect and edge_risk > 0.34:
            crop_mode = "safe_fit_blur_background"
            fallback = True
            visibility = max(visibility, 0.80)
            warnings.append("important_content_near_edge")
        elif input_aspect > 1.2 and crop_loss_ratio > 0.50 and edge_risk > 0.24:
            crop_mode = "safe_fit_blur_background"
            fallback = True
            visibility = max(visibility, 0.78)
            warnings.append("landscape_video_may_lose_side_content")
        elif input_aspect > target_aspect:
            crop_mode = "center_crop" if abs(saliency["center_x"] - 0.5) < 0.12 else "smart_center"

        if overlay_risk > 0.35:
            warnings.append("overlay_may_cover_important_content")
        safety = max(0.0, min(1.0, visibility * 0.60 + (1 - overlay_risk) * 0.20 + (1 - edge_risk) * 0.20))
        if zoom_motion > 30 and safety < 0.70:
            zoom_risk = min(1.0, (zoom_motion - 30) / 70 + (0.70 - safety))
            effective_zoom_motion = min(zoom_motion, 15)
            warnings.append("zoom_motion_may_cut_content")

        return CropAnalysisResult(
            source_path=source_path,
            start=start,
            end=end,
            input_width=media.width,
            input_height=media.height,
            target_width=target_width,
            target_height=target_height,
            recommended_crop=crop,
            crop_mode=crop_mode,
            visibility_score=round(visibility, 3),
            overlay_risk_score=round(overlay_risk, 3),
            edge_risk_score=round(edge_risk, 3),
            zoom_risk_score=round(zoom_risk, 3),
            overall_safety_score=round(safety, 3),
            warnings=_dedupe(warnings),
            fallback_used=fallback,
            effective_zoom_motion=effective_zoom_motion,
        )


def _base_crop_box(input_width: int, input_height: int, target_width: int, target_height: int) -> CropBox:
    target_aspect = target_width / target_height
    input_aspect = input_width / input_height
    if input_aspect > target_aspect:
        crop_width = max(1, int(round(input_height * target_aspect)))
        crop_height = input_height
        x = max(0, (input_width - crop_width) // 2)
        y = 0
    else:
        crop_width = input_width
        crop_height = max(1, int(round(input_width / target_aspect)))
        x = 0
        y = max(0, (input_height - crop_height) // 2)
    return CropBox(x=x, y=y, width=min(crop_width, input_width), height=min(crop_height, input_height))


def _crop_around_saliency(input_width: int, input_height: int, crop_width: int, crop_height: int, center_x: float, center_y: float) -> CropBox:
    x = int(round(center_x * input_width - crop_width / 2))
    y = int(round(center_y * input_height - crop_height / 2))
    x = max(0, min(x, max(0, input_width - crop_width)))
    y = max(0, min(y, max(0, input_height - crop_height)))
    return CropBox(x=x, y=y, width=min(crop_width, input_width), height=min(crop_height, input_height))


def _average_saliency(items: list[dict]) -> dict:
    if not items:
        return _neutral_saliency()
    keys = ["center_x", "center_y", "left_edge_score", "right_edge_score", "bottom_score", "center_score", "total_score"]
    return {key: sum(float(item[key]) for item in items) / len(items) for key in keys}


def _neutral_saliency() -> dict:
    return {
        "center_x": 0.5,
        "center_y": 0.5,
        "left_edge_score": 0.15,
        "right_edge_score": 0.15,
        "bottom_score": 0.15,
        "center_score": 0.4,
        "total_score": 0.2,
    }


def _overlay_risk(saliency: dict, overlay_height_ratio: float) -> float:
    ratio = max(0.0, min(0.6, overlay_height_ratio))
    return max(0.0, min(1.0, float(saliency["bottom_score"]) * (ratio / 0.22 if ratio else 0.0)))


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
