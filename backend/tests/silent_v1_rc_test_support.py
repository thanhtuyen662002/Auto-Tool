from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from app.modules.douyin_reup.douyin_schema import DouyinVideoItem
from app.modules.silent_immersive_reup.silent_schema import SilentReupPlan, SilentReupResult, SilentVisualSegment
from app.modules.silent_visual_tagging.visual_tag_schema import SegmentVisualTagResult, VideoVisualTagReport, VisualTag


def make_args(config: Path, **overrides) -> argparse.Namespace:
    values = {
        "config": str(config),
        "preset": None,
        "industry": None,
        "scan_only": False,
        "detect_only": False,
        "plan_only": False,
        "review_mode": True,
        "auto_render": False,
        "final_qa": False,
        "export_pack": False,
        "mock_ocr": False,
        "mock_tts": False,
        "debug": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def make_config(tmp_path: Path, video_names: list[str]) -> tuple[Path, Path, Path]:
    source = tmp_path / "source"
    source.mkdir()
    for name in video_names:
        (source / name).write_bytes(b"fake-video")
    output = tmp_path / "output"
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "project_name": "silent-rc-test",
                "source_folder": str(source),
                "output_folder": str(output),
                "product_context": {"industry": "kitchen_goods", "product_name": "Kitchen rack"},
                "settings": {
                    "enabled": True,
                    "preset_id": "silent_chill_immersive",
                    "silent_review_before_render": True,
                },
            }
        ),
        encoding="utf-8",
    )
    return config, source, output


def install_fake_flow(monkeypatch, rc_module, video_paths: list[Path], *, fail_names: set[str] | None = None) -> None:
    fail_names = fail_names or set()

    class FakeScanner:
        errors: list[str] = []

        def scan_folder(self, _folder):
            return [
                DouyinVideoItem(
                    path=str(path),
                    filename=path.name,
                    duration=4,
                    width=1080,
                    height=1920,
                    fps=30,
                    has_audio=False,
                )
                for path in video_paths
            ]

    class FakePipeline:
        def __init__(self, **_kwargs):
            self.last_plan_path = None
            self.last_ocr_source_srt_path = None

        def write_caption_srt(self, _plan, output_dir, filename):
            path = Path(output_dir) / filename
            path.write_text("1\n00:00:00,000 --> 00:00:04,000\nGóc bếp gọn hơn\n", encoding="utf-8")
            return str(path)

        def render_from_plan(self, plan, _settings, output_dir):
            output = Path(output_dir) / "silent_final.mp4"
            output.write_bytes(b"rendered")
            return SilentReupResult(
                input_video_path=plan.video_path,
                output_video_path=str(output),
                plan_path=self.last_plan_path,
                status="success",
            )

    class FakeService:
        def __init__(self, pipeline=None, **_kwargs):
            self.pipeline = pipeline or FakePipeline()
            self.detector = SimpleNamespace(detect=lambda _path: SimpleNamespace(has_speech=False))

        def build_plan(self, video_path, settings=None, output_dir=None, product_context=None):
            if Path(video_path).name in fail_names:
                raise RuntimeError("Cannot create visual segments for corrupt video")
            target = Path(output_dir)
            segment = SilentVisualSegment(
                id="seg_001",
                video_path=video_path,
                start=0,
                end=4,
                duration=4,
                primary_industry="kitchen_goods",
                primary_action="usage_demo",
                visual_tags=[VisualTag(tag="kitchen_goods", category="industry", confidence=0.9, source="product_context")],
                visual_tag_confidence=0.9,
            )
            report = VideoVisualTagReport(
                video_path=video_path,
                segment_results=[
                    SegmentVisualTagResult(
                        segment_id=segment.id,
                        video_path=video_path,
                        start=0,
                        end=4,
                        tags=segment.visual_tags,
                        primary_industry="kitchen_goods",
                        primary_action="usage_demo",
                        confidence=0.9,
                    )
                ],
                video_level_tags=segment.visual_tags,
                recommended_industry="kitchen_goods",
                recommended_strategy="chill_immersive",
                average_confidence=0.9,
                created_at="2026-06-12T00:00:00",
            )
            plan = SilentReupPlan(
                video_path=video_path,
                strategy=settings.silent_mode_strategy,
                has_speech=False,
                speech_score=0,
                visual_segments=[segment],
                captions=[
                    {
                        "index": 1,
                        "start": 0,
                        "end": 4,
                        "text": "Góc bếp gọn hơn",
                        "source": "template",
                        "selected_industry": "kitchen_goods",
                        "selected_intent": "demo",
                        "quality_score": 0.9,
                    }
                ],
                generate_voiceover=settings.generate_voiceover_for_silent_video,
                voiceover_script="Một gợi ý gọn gàng cho căn bếp." if settings.generate_voiceover_for_silent_video else None,
                recommended_audio_mode="original_audio_plus_bgm",
                visual_tagging={
                    "recommended_industry": "kitchen_goods",
                    "recommended_strategy": "chill_immersive",
                    "average_confidence": 0.9,
                },
                visual_tag_report=report,
            )
            plan_path = target / "silent_reup_plan.json"
            plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
            (target / "visual_tag_report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
            (target / "caption_generation_log.json").write_text('{"status":"success"}', encoding="utf-8")
            (target / "silent_reup_log.json").write_text('{"status":"planned"}', encoding="utf-8")
            if plan.voiceover_script:
                (target / "voiceover_script.txt").write_text(plan.voiceover_script, encoding="utf-8")
            self.pipeline.last_plan_path = str(plan_path)
            return plan

    monkeypatch.setattr(rc_module, "DouyinFolderScanner", FakeScanner)
    monkeypatch.setattr(rc_module, "SilentReupPipeline", FakePipeline)
    monkeypatch.setattr(rc_module, "SilentReupService", FakeService)

