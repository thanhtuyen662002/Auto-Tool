from __future__ import annotations

from pathlib import Path

from app.modules.silent_immersive_reup.product_detector import SilentProductDetector
from app.modules.silent_immersive_reup.silent_schema import SilentVisualSegment, VisualSegmentType


class FakeVisionClient:
    def generate_json_with_images(self, prompt: str, image_paths: list[str]) -> dict:
        assert image_paths
        assert "Không được bịa brand" in prompt
        return {
            "candidates": [
                {
                    "display_name": "dụng cụ vệ sinh ly cốc",
                    "product_name": "",
                    "product_type": "dụng cụ vệ sinh ly cốc",
                    "industry": "cleaning_goods",
                    "certainty": "product_type",
                    "confidence": 0.86,
                    "visible_features": ["đầu chổi dài", "thao tác cọ bên trong ly"],
                    "use_cases": ["vệ sinh ly/cốc"],
                    "evidence": [
                        {
                            "source": "frame",
                            "value": "Frame 1 cho thấy sản phẩm đang cọ bên trong ly.",
                            "confidence": 0.82,
                        },
                        {
                            "source": "frame",
                            "value": "Frame 2 tiếp tục thấy cùng dụng cụ vệ sinh ly cốc.",
                            "confidence": 0.8,
                        }
                    ],
                }
            ],
            "warnings": [],
        }


class FakeObservationOnlyClient:
    def generate_json_with_images(self, prompt: str, image_paths: list[str]) -> dict:
        assert image_paths
        return {
            "frame_observations": [
                {
                    "frame_label": "frame_001",
                    "product_type": "dung cu ve sinh ly coc",
                    "industry": "cleaning_goods",
                    "primary_object": "ban chai ly",
                    "is_product_visible": True,
                    "confidence": 0.72,
                    "visible_features": ["co dau choi dai"],
                    "evidence": "Frame 1 co thao tac co ly.",
                },
                {
                    "frame_label": "frame_002",
                    "product_type": "dung cu ve sinh ly coc",
                    "industry": "cleaning_goods",
                    "primary_object": "ban chai ly",
                    "is_product_visible": True,
                    "confidence": 0.75,
                    "visible_features": ["xuat hien lap lai"],
                    "evidence": "Frame 2 thay cung vat the.",
                },
                {
                    "frame_label": "frame_003",
                    "product_type": "tay",
                    "industry": "general_product",
                    "primary_object": "tay",
                    "is_product_visible": False,
                    "confidence": 0.35,
                    "noise_objects": ["tay", "ban"],
                    "evidence": "Frame nhieu chi thay tay.",
                },
            ],
            "warnings": [],
        }


def test_ai_vision_detection_updates_product_context(tmp_path):
    frame = tmp_path / "frame.jpg"
    frame.write_bytes(b"fake image")
    segment = SilentVisualSegment(
        id="seg_001",
        video_path="clip.mp4",
        start=0,
        end=2,
        duration=2,
        segment_type=VisualSegmentType.demo,
        visual_score=0.8,
        representative_frame_path=str(frame),
    )

    report = SilentProductDetector(vision_client=FakeVisionClient()).detect(
        video_path="clip.mp4",
        segments=[segment],
        visual_tag_report=None,
        product_context={},
        gemini_api_keys=["test-key"],
    )

    assert report.provider == "gemini_vision"
    assert report.top_candidate is not None
    assert report.top_candidate.product_type == "dụng cụ vệ sinh ly cốc"
    assert report.context_updates["product_name"] == "dụng cụ vệ sinh ly cốc"
    assert report.context_updates["industry"] == "cleaning_goods"


def test_frame_observation_vote_handles_noisy_frames(tmp_path):
    frames = []
    for index in range(3):
        frame = tmp_path / f"frame_{index}.jpg"
        frame.write_bytes(b"fake image")
        frames.append(frame)
    segments = [
        SilentVisualSegment(
            id=f"seg_{index + 1:03d}",
            video_path="clip.mp4",
            start=index,
            end=index + 1,
            duration=1,
            segment_type=VisualSegmentType.demo,
            visual_score=0.7,
            representative_frame_path=str(frame),
        )
        for index, frame in enumerate(frames)
    ]

    report = SilentProductDetector(vision_client=FakeObservationOnlyClient()).detect(
        video_path="clip.mp4",
        segments=segments,
        visual_tag_report=None,
        product_context={},
        gemini_api_keys=["test-key"],
    )

    assert report.provider == "gemini_vision"
    assert report.top_candidate is not None
    assert report.top_candidate.product_type == "dung cu ve sinh ly coc"
    assert report.top_candidate.confidence > 0.78
    assert report.context_updates["product_name"] == "dung cu ve sinh ly coc"
    assert len(report.frame_observations) == 3


def test_single_frame_product_detection_does_not_lock_product_name(tmp_path):
    frame = tmp_path / "frame.jpg"
    frame.write_bytes(b"fake image")
    segment = SilentVisualSegment(
        id="seg_001",
        video_path="clip.mp4",
        start=0,
        end=2,
        duration=2,
        segment_type=VisualSegmentType.demo,
        visual_score=0.8,
        representative_frame_path=str(frame),
    )

    class SingleFrameVisionClient:
        def generate_json_with_images(self, prompt: str, image_paths: list[str]) -> dict:
            return {
                "candidates": [
                    {
                        "display_name": "dong ho hen gio bep",
                        "product_type": "dong ho hen gio bep",
                        "industry": "kitchen_goods",
                        "certainty": "product_type",
                        "confidence": 0.97,
                        "evidence": [{"source": "frame", "value": "Frame 1 thay dong ho hen gio.", "confidence": 0.95}],
                    }
                ]
            }

    report = SilentProductDetector(vision_client=SingleFrameVisionClient()).detect(
        video_path="clip.mp4",
        segments=[segment],
        visual_tag_report=None,
        product_context={},
        gemini_api_keys=["test-key"],
    )

    assert report.top_candidate is not None
    assert "single_frame_evidence" in report.top_candidate.risk_flags
    assert report.top_candidate.confidence <= 0.62
    assert "product_name" not in report.context_updates


def test_fallback_detection_does_not_invent_exact_product(tmp_path):
    frame = tmp_path / "frame.jpg"
    frame.write_bytes(b"fake image")
    segment = SilentVisualSegment(
        id="seg_001",
        video_path="clip.mp4",
        start=0,
        end=2,
        duration=2,
        segment_type=VisualSegmentType.demo,
        visual_score=0.8,
        primary_industry="cleaning_goods",
        representative_frame_path=str(frame),
    )

    report = SilentProductDetector().detect(
        video_path=str(Path("clip.mp4")),
        segments=[segment],
        visual_tag_report=None,
        product_context={},
        gemini_api_keys=[],
    )

    assert report.provider == "heuristic_fallback"
    assert report.top_candidate is not None
    assert report.top_candidate.certainty == "category_only"
    assert report.top_candidate.product_name == ""
    assert report.context_updates.get("product_name") is None
    assert report.top_candidate.display_name == "dụng cụ vệ sinh"
