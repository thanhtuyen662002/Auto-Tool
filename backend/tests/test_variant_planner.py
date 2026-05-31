from __future__ import annotations

from app.modules.script_variants.variant_registry import VariantPlanner, list_variant_styles


def test_plan_variants_output_count_three_are_different():
    planned = VariantPlanner().plan_variants(3, None)

    assert len(planned) == 3
    assert len({style.id for style in planned}) == 3


def test_plan_variants_cycles_without_consecutive_duplicates():
    planned = VariantPlanner().plan_variants(14, None)

    assert len(planned) == 14
    for previous, current in zip(planned, planned[1:]):
        assert previous.id != current.id


def test_plan_variants_prefers_styles_matching_timeline_template():
    planned = VariantPlanner().plan_variants(3, "fast_tiktok_recut")

    assert planned[0].id == "fast_sales"


def test_registry_has_required_variant_styles():
    ids = {style.id for style in list_variant_styles()}

    assert {
        "problem_hook",
        "reviewer_natural",
        "benefit_first",
        "use_case_scene",
        "fast_sales",
        "comparison_soft",
    }.issubset(ids)

