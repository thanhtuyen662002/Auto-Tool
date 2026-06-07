from __future__ import annotations

from app.modules.content_safety.script_safety_checker import ScriptSafetyChecker
from app.modules.render_worker.output_pipeline import _guard_script_or_fallback
from app.modules.script_writer.script_writer import ProductVideoScript
from app.schemas.project_schema import (
    AISettings,
    EffectSettings,
    ProductInfo,
    ProjectConfig,
    RenderSettings,
)


def test_script_placeholder_returns_error() -> None:
    result = ScriptSafetyChecker().check_script_against_product(
        _script("Video cho {product_name}"),
        _product(),
        target_duration=12,
    )

    assert result.passed is False
    assert any(issue.category == "placeholder" for issue in result.issues)


def test_script_unsupported_spec_claim_returns_warning() -> None:
    result = ScriptSafetyChecker().check_script_against_product(
        _script("Máy có pin 5000mAh và chống nước IPX7."),
        _product(),
        target_duration=12,
    )

    assert result.passed is True
    assert any(issue.category == "unsupported_spec_claim" for issue in result.issues)


def test_unsafe_generated_script_uses_fallback() -> None:
    output_log = {"warnings": [], "errors": []}
    guarded = _guard_script_or_fallback(_script("{product_name}"), _config(), 1, output_log)

    assert guarded.hook != "{product_name}"
    assert output_log["script_safety"]["fallback_used"] is True
    assert any("fallback" in warning for warning in output_log["warnings"])


def _script(text: str) -> ProductVideoScript:
    return ProductVideoScript.model_validate(
        {
            "hook": text,
            "voiceover": [{"time_hint": "0-4s", "text": text}],
            "subtitles": [{"start_hint": 0, "end_hint": 4, "text": text}],
            "cta": "Xem ngay",
            "caption": text,
            "hashtags": ["#review"],
        }
    )


def _product() -> ProductInfo:
    return ProductInfo(
        name="Máy chiếu KAW",
        brand="KAW",
        description="Máy chiếu nhỏ gọn hỗ trợ 4K và Android 9.0.",
        features=["Hỗ trợ 4K", "Android 9.0"],
        specs=[],
        cta="Xem ngay",
    )


def _config() -> ProjectConfig:
    return ProjectConfig(
        project_name="safety-test",
        source_folder=".",
        output_folder=".",
        product=_product(),
        render=RenderSettings(output_count=1, duration=12, aspect_ratio="9:16", resolution="1080x1920", fps=30),
        effects=EffectSettings(
            cut_intensity=70,
            speed_variation=30,
            grain=0,
            zoom_motion=0,
            overlay_height=33,
            subtitle_size=84,
        ),
        ai=AISettings(text_model="gemini-test", tone="friendly_reviewer", language="vi", gemini_api_keys=[]),
    )
