from fastapi.testclient import TestClient

from app import database
from app.api import create_app
from app.modules.silent_immersive_reup.silent_schema import SilentReupPlan, SilentVisualSegment, VisualSegmentType


def _plan(video_path: str) -> SilentReupPlan:
    return SilentReupPlan(
        video_path=video_path,
        strategy="chill_immersive",
        has_speech=False,
        speech_score=0.0,
        visual_segments=[
            SilentVisualSegment(
                id="seg_1",
                video_path=video_path,
                start=0,
                end=2,
                duration=2,
                segment_type=VisualSegmentType.demo,
                motion_score=0.8,
            )
        ],
        captions=[{"index": 1, "start": 0, "end": 2, "text": "Caption cũ", "source": "template", "segment_id": "seg_1"}],
        recommended_audio_mode="original_audio_plus_bgm",
    )


def test_visual_tag_vocabulary_report_and_user_override(tmp_path, monkeypatch):
    database.DB_PATH = tmp_path / "visual-tags.db"
    video = tmp_path / "厨房_clip.mp4"
    video.write_bytes(b"fake")

    class FakeService:
        def build_plan(self, video_path, settings=None, output_dir=None, product_context=None, **_kwargs):
            return _plan(video_path)

    monkeypatch.setattr("app.api.SilentReupService", FakeService)
    monkeypatch.setattr("app.api.start_background_dependency_warmup", lambda **_kwargs: None)
    with TestClient(create_app()) as client:
        created = client.post(
            "/api/silent-reup/plan",
            json={"video_path": str(video), "settings": {}, "product_context": {"industry": "kitchen_goods"}},
        )
        plan_id = created.json()["plan_id"]
        vocabulary = client.get("/api/silent-reup/visual-tags/vocabulary")
        generated = client.post(f"/api/silent-reup/plans/{plan_id}/visual-tags")
        overridden = client.put(
            f"/api/silent-reup/plans/{plan_id}/segments/seg_1/tags",
            json={
                "segment_id": "seg_1",
                "tags": ["desk_setup", "desk_scene", "usage_demo"],
                "primary_industry": "desk_setup",
                "primary_scene": "desk_scene",
                "primary_action": "usage_demo",
            },
        )

    assert vocabulary.status_code == 200
    assert "kitchen_goods" in vocabulary.json()["industry"]
    assert generated.status_code == 200
    assert generated.json()["report"]["recommended_industry"] == "kitchen_goods"
    segment = overridden.json()["plan"]["visual_segments"][0]
    assert segment["primary_industry"] == "desk_setup"
    assert all(tag["source"] == "user" and tag["confidence"] == 1.0 for tag in segment["visual_tags"])
