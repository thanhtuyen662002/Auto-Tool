from __future__ import annotations

from app.modules.timeline_templates.template_registry import DEFAULT_TEMPLATE_ID, get_timeline_template, list_timeline_templates


def test_registry_returns_default_templates():
    templates = list_timeline_templates()
    ids = {template.id for template in templates}

    assert "product_showcase_clean" in ids
    assert "ugc_reviewer_natural" in ids
    assert "fast_tiktok_recut" in ids
    assert "problem_solution" in ids


def test_template_slot_ratios_are_valid_and_do_not_overlap():
    for template in list_timeline_templates():
        previous_end = 0.0
        assert template.slots[0].start_ratio == 0
        assert template.slots[-1].end_ratio == 1
        for slot in template.slots:
            assert slot.start_ratio >= previous_end
            assert slot.end_ratio > slot.start_ratio
            previous_end = slot.end_ratio


def test_unknown_template_id_falls_back_to_default():
    template = get_timeline_template("does_not_exist")

    assert template.id == DEFAULT_TEMPLATE_ID

