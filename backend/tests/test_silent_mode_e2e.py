import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from app.modules.douyin_reup.douyin_schema import DouyinVideoItem
from app.modules.silent_immersive_reup.silent_schema import SilentReupPlan, SilentVisualSegment
from app.tools import silent_mode_e2e_test


def test_silent_e2e_creates_plan_and_review_document(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    video = source / "clip.mp4"
    video.write_bytes(b"fake")
    output = tmp_path / "output"
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"source_folder": str(source), "output_folder": str(output), "settings": {"enabled": True}}), encoding="utf-8")

    class FakeScanner:
        errors = []

        def scan_folder(self, _folder):
            return [DouyinVideoItem(path=str(video), filename=video.name, duration=2, width=1080, height=1920, fps=30, has_audio=False)]

    class FakePipeline:
        last_ocr_source_srt_path = None
        last_plan_path = str(output / "video_001" / "silent_reup_plan.json")

        def write_caption_srt(self, plan, output_dir, filename):
            path = Path(output_dir) / filename
            path.write_text("1\n00:00:00,000 --> 00:00:02,000\nCaption test\n", encoding="utf-8")
            return str(path)

    class FakeService:
        detector = SimpleNamespace(detect=lambda _path: SimpleNamespace(has_speech=False))
        pipeline = FakePipeline()

        def build_plan(self, video_path, **_kwargs):
            return SilentReupPlan(
                video_path=video_path,
                strategy="chill_immersive",
                has_speech=False,
                speech_score=0,
                visual_segments=[SilentVisualSegment(id="seg", video_path=video_path, start=0, end=2, duration=2)],
                captions=[{"index": 1, "start": 0, "end": 2, "text": "Caption test", "source": "template"}],
                recommended_audio_mode="original_audio_plus_bgm",
            )

    monkeypatch.setattr(silent_mode_e2e_test, "DouyinFolderScanner", FakeScanner)
    monkeypatch.setattr(silent_mode_e2e_test, "SilentReupService", FakeService)
    args = argparse.Namespace(config=str(config), scan_only=False, detect_only=False, plan_only=False, review_mode=True, auto_render=False, final_qa=False, export_pack=False, mock_ocr=True, mock_tts=True, debug=False)
    result = silent_mode_e2e_test.run_e2e(args)

    assert result["status"] in {"success", "success_with_warnings"}
    assert result["silent_detected"] == 1
    assert result["plans_created"] == 1
    assert result["review_documents_created"] == 1
