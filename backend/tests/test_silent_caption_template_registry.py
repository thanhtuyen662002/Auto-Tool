from app.modules.content_safety.product_claim_checker import RISKY_CLAIM_TERMS, SENSITIVE_CLAIM_TERMS
from app.modules.silent_caption_templates import SILENT_CAPTION_TEMPLATES, SilentCaptionIndustry, SilentCaptionIntent


def test_registry_has_at_least_120_safe_templates():
    assert len(SILENT_CAPTION_TEMPLATES) >= 120
    assert set(item.industry for item in SILENT_CAPTION_TEMPLATES) == set(SilentCaptionIndustry)
    assert set(item.intent for item in SILENT_CAPTION_TEMPLATES) == set(SilentCaptionIntent)
    texts = [item.text.casefold() for item in SILENT_CAPTION_TEMPLATES]
    assert not any(term in text for text in texts for term in [*RISKY_CLAIM_TERMS, *SENSITIVE_CLAIM_TERMS])


def test_registry_ids_and_texts_are_unique():
    assert len({item.id for item in SILENT_CAPTION_TEMPLATES}) == len(SILENT_CAPTION_TEMPLATES)
    assert len({item.text.casefold() for item in SILENT_CAPTION_TEMPLATES}) == len(SILENT_CAPTION_TEMPLATES)
