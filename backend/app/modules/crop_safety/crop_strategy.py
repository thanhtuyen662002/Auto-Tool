from __future__ import annotations

from app.modules.crop_safety.crop_analyzer import CropAnalyzer
from app.modules.crop_safety.crop_schema import CropAnalysisResult, CropBox
from app.schemas.media_schema import MediaFile, VideoSegment
from app.schemas.project_schema import ProjectConfig


class CropStrategyService:
    def __init__(self, analyzer: CropAnalyzer | None = None) -> None:
        self.analyzer = analyzer or CropAnalyzer()

    def choose_crop_strategy(
        self,
        media_file: MediaFile,
        segment: VideoSegment | None,
        config: ProjectConfig,
    ) -> CropAnalysisResult:
        width, height = _parse_resolution(config.render.resolution)
        overlay_ratio = max(0.0, min(0.6, config.effects.overlay_height / 100))
        start = segment.start if segment else None
        end = segment.end if segment else None
        result = self.analyzer.analyze_video_or_segment(
            source_path=media_file.path,
            start=start,
            end=end,
            target_width=width,
            target_height=height,
            overlay_height_ratio=overlay_ratio,
            zoom_motion=config.effects.zoom_motion,
        )
        crop_settings = config.crop_safety
        center_crop = build_center_crop_box(media_file.width, media_file.height, width, height)
        if not crop_settings.enabled:
            return result.model_copy(update={"recommended_crop": center_crop, "crop_mode": "center_crop", "fallback_used": False})
        if crop_settings.mode == "center_crop":
            return result.model_copy(update={"recommended_crop": center_crop, "crop_mode": "center_crop", "fallback_used": False})
        if crop_settings.mode == "fit_blur_background":
            return result.model_copy(update={"crop_mode": "safe_fit_blur_background", "fallback_used": True})
        if result.crop_mode == "safe_fit_blur_background" and not crop_settings.allow_blur_background:
            warnings = [*result.warnings, "blur_background_disabled_fallback_center_crop"]
            return result.model_copy(
                update={
                    "recommended_crop": center_crop,
                    "crop_mode": "center_crop",
                    "fallback_used": False,
                    "warnings": warnings,
                }
            )
        if not crop_settings.reduce_zoom_on_risk:
            return result.model_copy(update={"effective_zoom_motion": config.effects.zoom_motion})
        return result


def build_crop_video_filter(
    crop_mode: str | None,
    crop_box,
    target_width: int,
    target_height: int,
    fps: int,
    speed: float,
    grain: int = 0,
) -> str:
    mode = crop_mode or "center_crop"
    if mode == "safe_fit_blur_background":
        filters = [
            f"scale={target_width}:{target_height}:force_original_aspect_ratio=increase",
            f"crop={target_width}:{target_height}",
            "boxblur=20:1[bg]",
            f"[0:v]scale={target_width}:{target_height}:force_original_aspect_ratio=decrease[fg]",
            "[bg][fg]overlay=(W-w)/2:(H-h)/2",
        ]
        tail = ["setsar=1", f"fps={fps}", f"setpts=PTS/{speed:.6f}"]
        if grain > 0:
            tail.append(f"noise=alls={max(1, min(100, grain))}:allf=t+u")
        return f"[0:v]{filters[0]},{filters[1]},{filters[2]};{filters[3]};{filters[4]},{','.join(tail)}"

    if mode == "no_crop_scale":
        filters = [
            f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease",
            f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black",
            "setsar=1",
            f"fps={fps}",
            f"setpts=PTS/{speed:.6f}",
        ]
    elif crop_box is not None and mode in {"smart_center", "center_crop", "top_crop", "bottom_crop"}:
        filters = [
            f"crop={crop_box.width}:{crop_box.height}:{crop_box.x}:{crop_box.y}",
            f"scale={target_width}:{target_height}",
            "setsar=1",
            f"fps={fps}",
            f"setpts=PTS/{speed:.6f}",
        ]
    else:
        filters = [
            f"scale={target_width}:{target_height}:force_original_aspect_ratio=increase",
            f"crop={target_width}:{target_height}",
            "setsar=1",
            f"fps={fps}",
            f"setpts=PTS/{speed:.6f}",
        ]
    if grain > 0:
        filters.append(f"noise=alls={max(1, min(100, grain))}:allf=t+u")
    return ",".join(filters)


def _parse_resolution(value: str) -> tuple[int, int]:
    width, height = value.lower().split("x")
    return int(width), int(height)


def build_center_crop_box(input_width: int, input_height: int, target_width: int, target_height: int) -> CropBox:
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
