from app.modules.silent_caption_templates import SilentCaptionTemplateService


def test_pick_template_by_industry_and_intent():
    service = SilentCaptionTemplateService()
    template = service.pick_template("kitchen_goods", "demo", "chill_immersive")
    assert template.industry.value == "kitchen_goods"
    assert template.intent.value == "demo"
    assert any(word in template.text.casefold() for word in ("bếp", "thao tác", "dùng"))


def test_missing_industry_falls_back_to_general_and_avoids_recent():
    service = SilentCaptionTemplateService()
    first = service.pick_template("missing", "hook", "chill_immersive")
    second = service.pick_template(
        "missing",
        "hook",
        "chill_immersive",
        avoid_recent_texts=[service.render_template(first)],
    )
    assert first.industry.value == "general_product"
    assert first.text != second.text
    assert len(service.render_template(second)) <= 56
