from __future__ import annotations

import pytest

from app.adapters.gemini_adapter import ScriptGenerationError
from app.modules.script_writer.prompts import build_product_video_script_prompt, variant_angle
from app.modules.script_writer.script_writer import ProductVideoScript, ScriptWriter
from app.schemas.project_schema import ProjectConfig


class StaticGeminiAdapter:
    def __init__(self, payload):
        self.payload = payload

    def generate_json(self, prompt: str) -> dict:
        return self.payload


class FailingGeminiAdapter:
    def generate_json(self, prompt: str) -> dict:
        raise ScriptGenerationError("boom")


def _config(duration: float = 12) -> ProjectConfig:
    return ProjectConfig.model_validate(
        {
            "project_name": "test",
            "source_folder": "source",
            "output_folder": "output",
            "product": {
                "name": "Máy chiếu test",
                "brand": "KAW",
                "description": "Mô tả sản phẩm tiếng Việt.",
                "features": ["Hỗ trợ 4K", "Thiết kế nhỏ gọn"],
                "cta": "Xem chi tiết ngay",
            },
            "render": {
                "output_count": 1,
                "duration": duration,
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
        }
    )


def test_prompt_is_vietnamese_and_requests_json():
    config = _config()
    prompt = build_product_video_script_prompt(config.product, config.render, config.ai, output_index=2)

    assert "Bạn là chuyên gia" in prompt
    assert "Trả về JSON hợp lệ" in prompt
    assert "Schema JSON bắt buộc" in prompt
    assert variant_angle(2) in prompt


def test_generate_script_prepares_timing_from_adapter_payload():
    payload = {
        "hook": "Hook test",
        "voiceover": [
            {"time_hint": "0-2s", "text": "Câu một."},
            {"time_hint": "2-4s", "text": "Câu hai."},
        ],
        "subtitles": [{"start_hint": 0, "end_hint": 2, "text": "Câu một."}],
        "cta": "Xem ngay",
        "caption": "Caption",
        "hashtags": ["#test"],
    }
    script = ScriptWriter(StaticGeminiAdapter(payload)).generate_script(_config(duration=10), output_index=1)

    assert isinstance(script, ProductVideoScript)
    assert script.voiceover[0].time_hint == "0-5s"
    assert script.voiceover[-1].time_hint == "5-10s"
    assert script.subtitles[-1].end_hint == 10


def test_gemini_failure_raises_when_fallback_disabled(monkeypatch):
    monkeypatch.delenv("AUTO_TOOL_ALLOW_SCRIPT_FALLBACK", raising=False)

    with pytest.raises(ScriptGenerationError):
        ScriptWriter(FailingGeminiAdapter()).generate_script(_config(), output_index=1)


def test_fallback_script_is_valid_vietnamese(monkeypatch):
    monkeypatch.setenv("AUTO_TOOL_ALLOW_SCRIPT_FALLBACK", "1")

    script = ScriptWriter(FailingGeminiAdapter()).generate_script(_config(duration=12), output_index=1)
    combined_text = " ".join(line.text for line in script.voiceover)

    assert "Nếu bạn đang tìm" in combined_text
    assert "Náº" not in combined_text
    assert script.subtitles[-1].end_hint == 12
    assert script.cta == "Xem chi tiết ngay"
