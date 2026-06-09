from __future__ import annotations

from app.modules.product_reference_prompt.video_prompt_generator import ProductVideoPromptGenerator
from backend.tests.prompt_pack_helpers import add_main_asset, make_project


def test_video_prompt_pack_contains_reference_summary_storyboard_and_json(tmp_path) -> None:
    project_id = make_project(tmp_path)
    add_main_asset(project_id, tmp_path)

    prompt_pack = ProductVideoPromptGenerator().generate_video_prompt_pack(
        project_id,
        duration_seconds=8,
        scene_count=5,
        model_hint="omni",
    )

    assert prompt_pack.product_name == "Máy Chiếu 4K Android KAW XMAX10"
    assert "PRODUCT ACCURACY LOCK" in prompt_pack.video_prompt
    assert "Use the selected product reference images" in prompt_pack.video_prompt
    assert prompt_pack.json_prompt is not None
    assert prompt_pack.json_prompt["aspect_ratio"] == "9:16"
    assert prompt_pack.json_prompt["reference_assets"][0]["asset_id"] == "asset-main"
    assert "extra lens" in prompt_pack.negative_prompt


def test_video_prompt_pack_uses_generic_model_when_hint_is_generic(tmp_path) -> None:
    project_id = make_project(tmp_path)

    prompt_pack = ProductVideoPromptGenerator().generate_video_prompt_pack(project_id, model_hint="generic")

    assert prompt_pack.model_hint is None
    assert "Vertical 9:16 realistic product showcase" in (prompt_pack.short_prompt or "")
