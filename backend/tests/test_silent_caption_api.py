from fastapi.testclient import TestClient

from app import database
from app.api import create_app
from app.modules.silent_immersive_reup.silent_schema import SilentReupPlan, SilentVisualSegment, VisualSegmentType


def _plan(video_path: str, text: str = "Caption cũ") -> SilentReupPlan:
    return SilentReupPlan(
        video_path=video_path,
        strategy="chill_immersive",
        has_speech=False,
        speech_score=0.0,
        visual_segments=[SilentVisualSegment(id="seg_1", video_path=video_path, start=0, end=2, duration=2, segment_type=VisualSegmentType.product_reveal)],
        captions=[{"index": 1, "start": 0, "end": 2, "text": text, "source": "template"}],
        recommended_audio_mode="original_audio_plus_bgm",
    )


def test_template_api_and_regenerate_without_build_plan_analysis(tmp_path, monkeypatch):
    database.DB_PATH = tmp_path / "silent-caption-api.db"
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")
    calls = {"build": 0, "regenerate": 0}

    class FakeService:
        def build_plan(self, video_path, settings=None, output_dir=None, product_context=None):
            calls["build"] += 1
            return _plan(video_path)

        def regenerate_captions(self, plan, **kwargs):
            calls["regenerate"] += 1
            return _plan(plan.video_path, "Caption mới cho bếp")

    monkeypatch.setattr("app.api.SilentReupService", FakeService)
    monkeypatch.setattr("app.api.start_background_dependency_warmup", lambda **_kwargs: None)
    with TestClient(create_app()) as client:
        templates = client.get("/api/silent-caption-templates", params={"industry": "kitchen_goods"})
        industries = client.get("/api/silent-caption-templates/industries")
        created = client.post("/api/silent-reup/plan", json={"video_path": str(video), "settings": {}, "product_context": {}})
        regenerated = client.post(
            f"/api/silent-reup/plans/{created.json()['plan_id']}/regenerate-captions",
            json={"industry": "kitchen_goods", "tone": "natural", "strategy": "chill_immersive"},
        )
        review = client.post(f"/api/silent-reup/plans/{created.json()['plan_id']}/review-document")

    assert templates.status_code == 200 and templates.json()["total"] >= 16
    assert industries.status_code == 200 and len(industries.json()["items"]) == 8
    assert regenerated.status_code == 200
    assert review.status_code == 200 and review.json()["document_id"]
    assert regenerated.json()["plan"]["captions"][0]["text"] == "Caption mới cho bếp"
    assert calls == {"build": 1, "regenerate": 1}
