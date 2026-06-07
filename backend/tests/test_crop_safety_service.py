from __future__ import annotations

import json

from app.modules.crop_safety.crop_safety_service import CropSafetyService, summarize_crop_safety_for_output
from app.modules.crop_safety.crop_schema import CropAnalysisResult, CropBox
from app.modules.timeline_builder.timeline_builder import Timeline, TimelineClip
from app.schemas.media_schema import MediaFile, VideoSegment
from app.schemas.project_schema import ProjectConfig


class FakeStrategyService:
    def choose_crop_strategy(
        self,
        media_file: MediaFile,
        segment: VideoSegment | None,
        config: ProjectConfig,
    ) -> CropAnalysisResult:
        assert segment is not None
        return CropAnalysisResult(
            source_path=media_file.path,
            start=segment.start,
            end=segment.end,
            input_width=media_file.width,
            input_height=media_file.height,
            target_width=1080,
            target_height=1920,
            recommended_crop=CropBox(x=200, y=0, width=608, height=1080),
            crop_mode="safe_fit_blur_background",
            visibility_score=0.82,
            overlay_risk_score=0.16,
            edge_risk_score=0.45,
            zoom_risk_score=0.20,
            overall_safety_score=0.78,
            warnings=["important_content_near_edge"],
            fallback_used=True,
            effective_zoom_motion=15,
        )


def test_crop_safety_service_updates_timeline_clips_and_writes_report(tmp_path, monkeypatch) -> None:
    service = CropSafetyService(strategy_service=FakeStrategyService())
    monkeypatch.setattr(
        service,
        "_media_cache",
        {
            "source.mp4": MediaFile(
                path="source.mp4",
                duration=8,
                width=1920,
                height=1080,
                fps=30,
                has_audio=True,
                format_name="mov,mp4,m4a,3gp,3g2,mj2",
            )
        },
    )
    timeline = Timeline(
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

    report = service.analyze_timelines([timeline], _config(), tmp_path, project_id="project-1")

    assert report.total_clips_analyzed == 1
    assert report.fallback_to_blur_background == 1
    assert timeline.clips[0].crop_mode == "safe_fit_blur_background"
    assert timeline.clips[0].crop_box is not None
    assert timeline.clips[0].effective_zoom_motion == 15

    report_path = tmp_path / "crop_safety_report.json"
    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["project_id"] == "project-1"
    assert payload["warnings_summary"]["important_content_near_edge"] == 1

    output_summary = summarize_crop_safety_for_output(timeline)
    assert output_summary["fallback_to_blur_background"] == 1
    assert output_summary["warnings"]


def _config() -> ProjectConfig:
    return ProjectConfig.model_validate(
        {
            "project_name": "crop-service-test",
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
