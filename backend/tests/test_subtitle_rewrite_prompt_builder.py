from app.modules.subtitle_quality.subtitle_quality_schema import (
    SubtitleQualityIssue,
    SubtitleQualityIssueType,
    SubtitleQualitySeverity,
)
from app.modules.subtitle_rewrite.subtitle_rewrite_prompt_builder import build_subtitle_rewrite_prompt
from app.modules.subtitle_rewrite.subtitle_rewrite_schema import SubtitleRewriteStyle


def test_prompt_builder_contains_safety_rules_and_requested_context():
    prompt = build_subtitle_rewrite_prompt(
        source_text="Chinese source",
        original_translation="Ban dich hien tai qua dai",
        issues=[
            SubtitleQualityIssue(
                issue_type=SubtitleQualityIssueType.too_long,
                severity=SubtitleQualitySeverity.warning,
                message="Subtitle is too long.",
            )
        ],
        style=SubtitleRewriteStyle.clear_review,
        suggestion_count=3,
        max_chars=56,
        preserve_keywords=["Brand X", "30 ml"],
    )

    assert "Khong them y moi" in prompt
    assert "Giu nguyen ten rieng, thuong hieu, so lieu va don vi" in prompt
    assert "clear_review" in prompt
    assert "Brand X, 30 ml" in prompt
    assert '"suggestions"' in prompt
