from __future__ import annotations

from app.modules.product_reference_prompt.storyboard_generator import ProductStoryboardGenerator
from backend.tests.prompt_pack_helpers import make_project


def test_storyboard_generates_five_scenes_with_expected_total_duration(tmp_path) -> None:
    project_id = make_project(tmp_path)

    storyboard = ProductStoryboardGenerator().generate_storyboard(project_id, duration_seconds=8, scene_count=5)

    assert len(storyboard.scenes) == 5
    assert sum(scene.duration_seconds for scene in storyboard.scenes) == 8
    assert storyboard.scenes[0].scene_type == "hook_visual"
    assert storyboard.scenes[-1].scene_type == "cta"


def test_tech_industry_adds_tech_negative_prompt(tmp_path) -> None:
    project_id = make_project(tmp_path, industry_id="tech_electronics")

    storyboard = ProductStoryboardGenerator().generate_storyboard(project_id)

    assert "extra lens" in storyboard.negative_prompt
    assert "wrong ports" in storyboard.negative_prompt


def test_fashion_industry_adds_accuracy_notes_for_shape_and_color(tmp_path) -> None:
    project_id = make_project(tmp_path, industry_id="fashion_accessories")

    storyboard = ProductStoryboardGenerator().generate_storyboard(project_id)
    all_notes = "\n".join(note for scene in storyboard.scenes for note in scene.product_accuracy_notes)

    assert "form dáng" in all_notes
    assert "màu sắc" in all_notes
