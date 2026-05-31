from __future__ import annotations

import pytest

from app.adapters.gemini_adapter import ScriptGenerationError
from app.modules.render_worker.render_worker import _script_for_output
from app.modules.script_variants.script_variant_generator import ScriptVariantGenerator
from app.modules.script_writer.script_writer import ProductVideoScript
from app.schemas.project_schema import ProjectConfig


class FailingGeminiAdapter:
    def generate_json(self, prompt: str) -> dict:
        raise ScriptGenerationError("boom")


class StaticGeminiAdapter:
    def generate_json(self, prompt: str) -> dict:
        return {
            "variant_style_id": "problem_hook",
            "hook": "Hook từ Gemini",
            "voiceover": [
                {"time_hint": "0-3s", "text": "Đây là câu mở đầu ngắn."},
                {"time_hint": "3-6s", "text": "Sản phẩm có vài điểm đáng xem."},
                {"time_hint": "6-9s", "text": "Bạn có thể xem thêm trước khi chọn mua."},
            ],
            "subtitles": [{"start_hint": 0, "end_hint": 3, "text": "Đây là câu mở đầu ngắn."}],
            "cta": "Xem chi tiết ngay",
            "caption": "Caption ngắn.",
            "hashtags": ["#review", "#sanpham", "#muasam"],
        }


def test_failing_gemini_still_generates_enough_distinct_scripts():
    generator = ScriptVariantGenerator(FailingGeminiAdapter())

    scripts = generator.generate_variants(_config(output_count=6), 6, "ugc_reviewer_natural")

    assert len(scripts) == 6
    assert len(generator.results) == 6
    assert len({script.hook for script in scripts}) >= 4
    assert all(isinstance(script.hashtags, list) for script in scripts)
    assert all(script.variant_style_id for script in scripts)


def test_generated_script_matches_schema_and_has_no_placeholder():
    generator = ScriptVariantGenerator(StaticGeminiAdapter())

    [script] = generator.generate_variants(_config(output_count=1), 1, "problem_solution")
    dumped = script.model_dump_json()

    assert isinstance(script, ProductVideoScript)
    assert "{product_name}" not in dumped
    assert script.subtitles[-1].end_hint == 12
    assert max(len(line.text) for line in script.voiceover) < 260


def test_generator_falls_back_when_gemini_returns_placeholder():
    class PlaceholderGeminiAdapter:
        def generate_json(self, prompt: str) -> dict:
            return {
                "variant_style_id": "problem_hook",
                "hook": "{product_name}",
                "voiceover": [{"time_hint": "0-3s", "text": "{product_name}"}],
                "subtitles": [{"start_hint": 0, "end_hint": 3, "text": "{product_name}"}],
                "cta": "CTA",
                "caption": "Caption",
                "hashtags": ["#test"],
            }

    generator = ScriptVariantGenerator(PlaceholderGeminiAdapter())

    [script] = generator.generate_variants(_config(output_count=1), 1, "problem_solution")

    assert "{product_name}" not in script.model_dump_json()
    assert generator.warnings


def test_write_script_variants_report(tmp_path):
    generator = ScriptVariantGenerator(FailingGeminiAdapter())
    config = _config(output_count=2)
    generator.generate_variants(config, 2, "ugc_reviewer_natural")

    report_path = generator.write_report(tmp_path, config)

    assert report_path.endswith("script_variants.json")
    assert (tmp_path / "script_variants.json").exists()


def test_render_pipeline_selects_script_by_output_index():
    scripts = [
        ProductVideoScript(
            variant_style_id="one",
            hook="Hook one",
            voiceover=[{"time_hint": "0-1s", "text": "Một"}],
            subtitles=[{"start_hint": 0, "end_hint": 1, "text": "Một"}],
            cta="CTA",
            caption="Caption",
            hashtags=["#one"],
        ),
        ProductVideoScript(
            variant_style_id="two",
            hook="Hook two",
            voiceover=[{"time_hint": "0-1s", "text": "Hai"}],
            subtitles=[{"start_hint": 0, "end_hint": 1, "text": "Hai"}],
            cta="CTA",
            caption="Caption",
            hashtags=["#two"],
        ),
    ]

    assert _script_for_output(2, None, scripts).variant_style_id == "two"
    assert _script_for_output(1, scripts[0], scripts).variant_style_id == "one"
    with pytest.raises(ValueError):
        _script_for_output(3, None, scripts)


def _config(output_count: int = 3) -> ProjectConfig:
    return ProjectConfig.model_validate(
        {
            "project_name": "variant-test",
            "source_folder": "source",
            "output_folder": "output",
            "product": {
                "name": "Máy chiếu KAW XMAX10",
                "brand": "KAW",
                "description": "Máy chiếu giải trí gia đình nhỏ gọn, hỗ trợ 4K.",
                "features": ["Hỗ trợ 4K", "Thiết kế nhỏ gọn", "Phù hợp phòng ngủ"],
                "cta": "Xem chi tiết sản phẩm ngay",
            },
            "render": {
                "output_count": output_count,
                "duration": 12,
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
            "music": {
                "enabled": False,
                "source_folder": None,
                "source_file": None,
                "volume": 0.12,
                "fade_in": 0.5,
                "fade_out": 0.8,
            },
            "timeline": {
                "template_id": "ugc_reviewer_natural",
            },
        }
    )
