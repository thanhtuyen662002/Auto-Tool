from __future__ import annotations

from app.modules.cache.cache_service import CacheService
from app.modules.crop_safety.crop_safety_service import CropSafetyService
from app.modules.crop_safety.crop_schema import CropAnalysisResult, CropBox
from app.modules.timeline_builder.timeline_builder import Timeline, TimelineClip
from app.schemas.media_schema import MediaFile, VideoSegment
from app.schemas.project_schema import ProjectConfig


class CountingCropStrategy:
    def __init__(self) -> None:
        self.calls = 0

    def choose_crop_strategy(
        self,
        media_file: MediaFile,
        segment: VideoSegment | None,
        config: ProjectConfig,
    ) -> CropAnalysisResult:
        self.calls += 1
        assert segment is not None
        return CropAnalysisResult(
            source_path=media_file.path,
            start=segment.start,
            end=segment.end,
            input_width=media_file.width,
            input_height=media_file.height,
            target_width=1080,
            target_height=1920,
            recommended_crop=CropBox(x=100, y=0, width=607, height=1080),
            crop_mode="safe_fit_blur_background",
            visibility_score=0.8,
            overlay_risk_score=0.1,
            edge_risk_score=0.2,
            zoom_risk_score=0.2,
            overall_safety_score=0.82,
            warnings=[],
            fallback_used=True,
            effective_zoom_motion=20,
        )


def test_crop_safety_uses_cache_on_second_run(tmp_path) -> None:
    cache_service = CacheService(tmp_path / ".cache")
    strategy = CountingCropStrategy()
    media = MediaFile(
        path="source.mp4",
        duration=8,
        width=1920,
        height=1080,
        fps=30,
        has_audio=True,
        format_name="mov,mp4,m4a,3gp,3g2,mj2",
    )

    first_timeline = _timeline()
    first_service = CropSafetyService(strategy_service=strategy, cache_service=cache_service)
    first_service._media_cache = {"source.mp4": media}
    first_service.analyze_timelines([first_timeline], _config(), tmp_path, project_id="project-1")

    second_timeline = _timeline()
    second_service = CropSafetyService(strategy_service=strategy, cache_service=cache_service)
    second_service._media_cache = {"source.mp4": media}
    second_service.analyze_timelines([second_timeline], _config(), tmp_path, project_id="project-1")

    assert strategy.calls == 1
    assert first_timeline.clips[0].crop_cache_hit is False
    assert second_timeline.clips[0].crop_cache_hit is True


def _timeline() -> Timeline:
    return Timeline(
        output_index=1,
        target_duration=4,
        clips=[
            TimelineClip(
                source_path="source.mp4",
                start=0.5,
                end=3.5,
                duration=3,
                speed=1,
                segment_score=0.9,
            )
        ],
    )


def _config() -> ProjectConfig:
    return ProjectConfig.model_validate(
        {
            "project_name": "crop-cache-test",
            "source_folder": "source",
            "output_folder": "outputs",
            "product": {
                "name": "Máy chiếu KAW",
                "brand": "KAW",
                "description": "Máy chiếu nhỏ gọn.",
                "features": ["Hỗ trợ 4K"],
                "cta": "Xem ngay",
            },
            "render": {
                "output_count": 1,
                "duration": 8,
                "aspect_ratio": "9:16",
                "resolution": "1080x1920",
                "fps": 30,
            },
            "effects": {
                "cut_intensity": 70,
                "speed_variation": 30,
                "grain": 0,
                "zoom_motion": 50,
                "overlay_height": 33,
                "subtitle_size": 84,
            },
            "ai": {
                "text_model": "gemini-test",
                "tone": "friendly_reviewer",
                "language": "vi",
            },
        }
    )
