from __future__ import annotations

import json
from pathlib import Path

from app import database
from app.modules.content_manager.content_service import ContentService
from app.modules.script_variants.script_variant_generator import ScriptVariantGenerator
from app.modules.script_writer.script_writer import ScriptWriter
from app.schemas.project_schema import ProjectConfig


class CapturingGeminiAdapter:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate_json(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        return {
            "hook": "Hook công nghệ",
            "voiceover": [{"time_hint": "0-8s", "text": "Sản phẩm có vài điểm đáng chú ý khi dùng."}],
            "subtitles": [{"start_hint": 0, "end_hint": 8, "text": "Sản phẩm có vài điểm đáng chú ý khi dùng."}],
            "cta": "Xem ngay",
            "caption": "Caption công nghệ rõ ràng",
            "hashtags": ["#congnghe"],
        }


class FailingGeminiAdapter:
    def generate_json(self, prompt: str) -> dict:
        raise RuntimeError("boom")


def test_script_variant_prompt_receives_industry_context() -> None:
    adapter = CapturingGeminiAdapter()
    config = _config(industry_id="tech_electronics")

    scripts = ScriptVariantGenerator(adapter).generate_variants(config, output_count=1, timeline_template_id=None)

    assert "Caption tone" in adapter.prompts[0]
    assert "#congnghe" in adapter.prompts[0]
    assert "benefit_first" in adapter.prompts[0]
    assert scripts[0].industry_preset_id == "tech_electronics"
    assert scripts[0].caption_tone
    assert scripts[0].hashtag_suggestions_used[0] == "#congnghe"


def test_script_writer_fallback_uses_industry_hashtags(monkeypatch) -> None:
    monkeypatch.setenv("AUTO_TOOL_ALLOW_SCRIPT_FALLBACK", "1")

    script = ScriptWriter(FailingGeminiAdapter()).generate_script(_config(industry_id="beauty_cosmetics"))

    assert script.industry_preset_id == "beauty_cosmetics"
    assert "#lamdep" in script.hashtags
    assert "#lamdep" in script.hashtag_suggestions_used
    assert script.caption_tone


def test_content_manager_uses_industry_hashtags_when_script_has_none(tmp_path) -> None:
    project_id, output_dir = _seed_content_project(tmp_path)

    items = ContentService().get_content_items(project_id)

    assert len(items) == 1
    assert "#doan" in items[0].hashtags
    assert "#foodreview" in items[0].hashtags
    assert (output_dir / "content_items.json").exists()


def _seed_content_project(tmp_path: Path) -> tuple[str, Path]:
    database.DB_PATH = tmp_path / "industry-content.db"
    database.init_db()
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir()
    output_dir.mkdir()
    project_id = "industry-content"
    database.create_project(project_id, _config(industry_id="food_beverage", source_dir=source_dir, output_dir=output_dir).model_dump(mode="json"))

    script_path = output_dir / "video_001_script.json"
    script_path.write_text(
        json.dumps(
            {
                "hook": "Hook",
                "voiceover": [{"time_hint": "0-3s", "text": "Voice"}],
                "subtitles": [{"start_hint": 0, "end_hint": 3, "text": "Voice"}],
                "cta": "Xem ngay",
                "caption": "Caption không hashtag",
                "hashtags": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    timeline_path = output_dir / "video_001_timeline.json"
    timeline_path.write_text(json.dumps({"template_id": "ugc_reviewer_natural"}), encoding="utf-8")
    video_path = output_dir / "video_001.mp4"
    video_path.write_bytes(b"video")
    database.create_job("industry-content-job", project_id, preview_only=False, total_outputs=1)
    database.update_job(
        "industry-content-job",
        status="completed",
        output_folder=str(output_dir),
        results_json=json.dumps(
            {"outputs": [{"index": 1, "path": str(video_path), "script_file": str(script_path), "timeline_file": str(timeline_path)}]},
            ensure_ascii=False,
        ),
    )
    return project_id, output_dir


def _config(
    industry_id: str,
    source_dir: Path | str = "source",
    output_dir: Path | str = "output",
) -> ProjectConfig:
    return ProjectConfig.model_validate(
        {
            "project_name": "industry-script-test",
            "source_folder": str(source_dir),
            "output_folder": str(output_dir),
            "product": {
                "name": "Sản phẩm test",
                "brand": "Brand",
                "description": "Mô tả test",
                "features": ["Tính năng"],
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
                "zoom_motion": 0,
                "overlay_height": 33,
                "subtitle_size": 84,
            },
            "ai": {
                "text_model": "gemini-test",
                "tone": "friendly_reviewer",
                "language": "vi",
                "gemini_api_keys": [],
            },
            "industry": {"preset_id": industry_id},
            "script_variation": {"mode": "auto_mix", "preferred_variant_ids": []},
        }
    )

