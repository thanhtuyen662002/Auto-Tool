from __future__ import annotations

from app.modules.crop_safety.crop_schema import CropAnalysisResult, CropBox
from app.modules.crop_safety.crop_strategy import CropStrategyService
from app.schemas.media_schema import MediaFile, VideoSegment
from app.schemas.project_schema import ProjectConfig


class FakeAnalyzer:
    def __init__(self, crop_mode: str = "safe_fit_blur_background") -> None:
        self.crop_mode = crop_mode

    def analyze_video_or_segment(self, **kwargs) -> CropAnalysisResult:
        return CropAnalysisResult(
            source_path=kwargs["source_path"],
            start=kwargs.get("start"),
            end=kwargs.get("end"),
            input_width=1920,
            input_height=1080,
            target_width=kwargs["target_width"],
            target_height=kwargs["target_height"],
            recommended_crop=CropBox(x=0, y=0, width=608, height=1080),
            crop_mode=self.crop_mode,
            visibility_score=0.80,
            overlay_risk_score=0.10,
            edge_risk_score=0.52,
            zoom_risk_score=0.20,
            overall_safety_score=0.74,
            warnings=["important_content_near_edge"],
            fallback_used=self.crop_mode == "safe_fit_blur_background",
            effective_zoom_motion=15,
        )


def test_crop_strategy_can_disable_smart_crop_and_force_center_crop() -> None:
    config = _config({"enabled": False})
    result = CropStrategyService(FakeAnalyzer()).choose_crop_strategy(_media(), _segment(), config)

    assert result.crop_mode == "center_crop"
    assert result.fallback_used is False
    assert result.recommended_crop.x == 656
    assert result.recommended_crop.width == 608


def test_crop_strategy_respects_blur_background_disabled() -> None:
    config = _config({"allow_blur_background": False})
    result = CropStrategyService(FakeAnalyzer()).choose_crop_strategy(_media(), _segment(), config)

    assert result.crop_mode == "center_crop"
    assert "blur_background_disabled_fallback_center_crop" in result.warnings
    assert result.recommended_crop.x == 656


def test_crop_strategy_fit_blur_mode_forces_safe_fit() -> None:
    config = _config({"mode": "fit_blur_background"})
    result = CropStrategyService(FakeAnalyzer(crop_mode="center_crop")).choose_crop_strategy(_media(), _segment(), config)

    assert result.crop_mode == "safe_fit_blur_background"
    assert result.fallback_used is True


def _media() -> MediaFile:
    return MediaFile(
        path="source.mp4",
        duration=8.0,
        width=1920,
        height=1080,
        fps=30,
        has_audio=True,
        format_name="mov,mp4,m4a,3gp,3g2,mj2",
    )


def _segment() -> VideoSegment:
    return VideoSegment(source_path="source.mp4", start=0.5, end=4.0, duration=3.5, score=0.8)


def _config(crop_safety_patch: dict | None = None) -> ProjectConfig:
    payload = {
        "project_name": "crop-strategy-test",
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
        "crop_safety": {
            "enabled": True,
            "mode": "auto_safe",
            "allow_blur_background": True,
            "reduce_zoom_on_risk": True,
            "reduce_overlay_on_risk": True,
            **(crop_safety_patch or {}),
        },
    }
    return ProjectConfig.model_validate(payload)
