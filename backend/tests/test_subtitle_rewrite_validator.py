from app.modules.subtitle_rewrite.subtitle_rewrite_validator import SubtitleRewriteValidator


def test_validator_rejects_empty_and_markdown_or_json():
    validator = SubtitleRewriteValidator()

    valid_empty, empty_warnings = validator.validate_suggestion(None, "Ban dich", "", [])
    valid_json, json_warnings = validator.validate_suggestion(None, "Ban dich", '{"translation":"Moi"}', [])

    assert valid_empty is False
    assert any("empty" in warning for warning in empty_warnings)
    assert valid_json is False
    assert any("markdown or JSON" in warning for warning in json_warnings)


def test_validator_rejects_missing_numbers_keywords_and_forbidden_claims():
    validator = SubtitleRewriteValidator()

    valid, warnings = validator.validate_suggestion(
        None,
        "Brand X co chai 30 ml",
        "San pham tot nhat cho ban",
        ["Brand X"],
    )

    assert valid is False
    assert any("Brand X" in warning for warning in warnings)
    assert any("30ml" in warning for warning in warnings)
    assert any("Forbidden claim" in warning for warning in warnings)
