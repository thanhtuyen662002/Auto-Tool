from __future__ import annotations

from app.modules.content_manager.content_schema import OutputContentItem
from app.modules.content_safety.caption_safety_checker import CaptionSafetyChecker, normalize_hashtags_for_safety
from app.modules.content_safety.product_claim_checker import ProductClaimChecker
from app.modules.content_safety.safety_schema import SafetyCheckResult, merge_safety_results
from app.modules.content_safety.script_safety_checker import ScriptSafetyChecker
from app.modules.script_writer.script_writer import ProductVideoScript
from app.schemas.project_schema import ProductInfo, ProjectConfig


class SafetyGuardService:
    def check_before_render(self, project_config: ProjectConfig) -> SafetyCheckResult:
        industry_id = project_config.industry.preset_id if project_config.industry else None
        return ProductClaimChecker().check_product_info(project_config.product, industry_id)

    def check_script_output(
        self,
        script: ProductVideoScript,
        product: ProductInfo,
        target_duration: float | None = None,
    ) -> SafetyCheckResult:
        return ScriptSafetyChecker().check_script_against_product(script, product, target_duration=target_duration)

    def check_content_items(
        self,
        items: list[OutputContentItem],
        product: ProductInfo,
    ) -> SafetyCheckResult:
        checker = CaptionSafetyChecker()
        results: list[SafetyCheckResult] = []
        for item in items:
            normalized_hashtags = normalize_hashtags_for_safety(item.hashtags)
            results.append(checker.check_caption(item.caption, normalized_hashtags, product))
        return merge_safety_results(*results)
