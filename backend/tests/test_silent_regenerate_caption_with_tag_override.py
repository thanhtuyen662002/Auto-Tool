from fastapi.testclient import TestClient

from app import database
from app.api import create_app
from app.modules.silent_immersive_reup.silent_schema import SilentReupPlan, SilentVisualSegment, VisualSegmentType


def test_regenerate_after_override_does_not_rebuild_or_analyze_video(tmp_path, monkeypatch):
    database.DB_PATH = tmp_path / "regenerate-tags.db"
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")
    calls = {"build": 0, "regenerate": 0}

    class FakeService:
        def build_plan(self, video_path, settings=None, output_dir=None, product_context=None, **_kwargs):
            calls["build"] += 1
            return SilentReupPlan(
                video_path=video_path,
                strategy="chill_immersive",
                has_speech=False,
                speech_score=0,
                visual_segments=[SilentVisualSegment(id="seg_1", video_path=video_path, start=0, end=2, duration=2, segment_type=VisualSegmentType.demo)],
                captions=[{"index": 1, "start": 0, "end": 2, "text": "Caption cũ", "source": "template"}],
                recommended_audio_mode="original_audio_plus_bgm",
            )

        def regenerate_captions(self, plan, **kwargs):
            calls["regenerate"] += 1
            assert plan.visual_segments[0].primary_industry == "kitchen_goods"
            return plan.model_copy(update={"captions": [{"index": 1, "start": 0, "end": 2, "text": "Caption bếp mới", "source": "template"}]})

    monkeypatch.setattr("app.api.SilentReupService", FakeService)
    monkeypatch.setattr("app.api.start_background_dependency_warmup", lambda **_kwargs: None)
    with TestClient(create_app()) as client:
        created = client.post("/api/silent-reup/plan", json={"video_path": str(video), "settings": {}, "product_context": {}})
        plan_id = created.json()["plan_id"]
        client.put(
            f"/api/silent-reup/plans/{plan_id}/segments/seg_1/tags",
            json={"tags": ["kitchen_goods", "kitchen_scene", "usage_demo"], "primary_industry": "kitchen_goods", "primary_action": "usage_demo"},
        )
        regenerated = client.post(
            f"/api/silent-reup/plans/{plan_id}/regenerate-captions",
            json={"industry": "auto", "tone": "natural", "use_visual_tags": True, "respect_user_tag_overrides": True},
        )

    assert regenerated.status_code == 200
    assert regenerated.json()["plan"]["captions"][0]["text"] == "Caption bếp mới"
    assert calls == {"build": 1, "regenerate": 1}
