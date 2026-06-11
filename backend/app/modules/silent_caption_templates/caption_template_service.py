from __future__ import annotations

from difflib import SequenceMatcher

from app.modules.content_safety.product_claim_checker import RISKY_CLAIM_TERMS, SENSITIVE_CLAIM_TERMS
from app.modules.silent_caption_templates.caption_template_registry import SILENT_CAPTION_TEMPLATES
from app.modules.silent_caption_templates.caption_template_schema import (
    SilentCaptionIndustry,
    SilentCaptionIntent,
    SilentCaptionTemplate,
)


TONE_ALIASES = {
    "natural": "natural",
    "cute": "cute",
    "clean_review": "clean_review",
    "sales_light": "sales_light",
    "chill": "chill",
}


class SilentCaptionTemplateService:
    def __init__(self, templates: list[SilentCaptionTemplate] | None = None) -> None:
        self.templates = list(templates or SILENT_CAPTION_TEMPLATES)

    def list_templates(
        self,
        industry: str | None = None,
        intent: str | None = None,
        strategy: str | None = None,
    ) -> list[SilentCaptionTemplate]:
        industry_value = _industry(industry) if industry else None
        intent_value = _intent(intent) if intent else None
        return [
            template
            for template in self.templates
            if (industry_value is None or template.industry == industry_value)
            and (intent_value is None or template.intent == intent_value)
            and (not strategy or template.strategy in {"all", strategy})
        ]

    def pick_template(
        self,
        industry: str,
        intent: str,
        strategy: str,
        product_context: dict | None = None,
        avoid_recent_texts: list[str] | None = None,
        tone: str = "natural",
    ) -> SilentCaptionTemplate:
        candidates = self._eligible(industry, intent, strategy, product_context)
        if not candidates:
            candidates = self._eligible(SilentCaptionIndustry.general_product.value, intent, strategy, product_context)
        if not candidates:
            candidates = self._eligible(SilentCaptionIndustry.general_product.value, SilentCaptionIntent.hook.value, strategy, product_context)
        if not candidates:
            raise LookupError("No eligible silent caption template found.")

        recent = [" ".join(text.casefold().split()) for text in (avoid_recent_texts or []) if text.strip()]
        tone_key = TONE_ALIASES.get(tone.strip().casefold(), "natural")
        ranked = sorted(
            candidates,
            key=lambda item: (
                0 if tone_key == item.tone or tone_key in item.tags else 1,
                max((_similarity(item.text, old) for old in recent), default=0.0),
                item.id,
            ),
        )
        for candidate in ranked:
            rendered = self.render_template(candidate, product_context)
            if rendered.casefold() not in recent and all(_similarity(rendered, old) < 0.88 for old in recent[-20:]):
                return candidate
        compatible = self._compatible_candidates(industry, intent, strategy, product_context)
        compatible_ranked = sorted(
            compatible,
            key=lambda item: (
                0 if tone_key == item.tone or tone_key in item.tags else 1,
                max((_similarity(item.text, old) for old in recent), default=0.0),
                item.id,
            ),
        )
        for candidate in compatible_ranked:
            rendered = self.render_template(candidate, product_context)
            if rendered.casefold() not in recent and all(_similarity(rendered, old) < 0.88 for old in recent[-20:]):
                return candidate
        for candidate in compatible_ranked:
            if self.render_template(candidate, product_context).casefold() not in recent:
                return candidate
        global_candidates: list[SilentCaptionTemplate] = []
        for candidate_industry in SilentCaptionIndustry:
            for candidate_intent in (
                [SilentCaptionIntent.cta]
                if _intent(intent) == SilentCaptionIntent.cta
                else [item for item in SilentCaptionIntent if item != SilentCaptionIntent.cta]
            ):
                global_candidates.extend(
                    self._eligible(
                        candidate_industry.value,
                        candidate_intent.value,
                        strategy,
                        product_context,
                    )
                )
        for candidate in sorted(global_candidates, key=lambda item: item.id):
            if self.render_template(candidate, product_context).casefold() not in recent:
                return candidate
        return ranked[0]

    def render_template(
        self,
        template: SilentCaptionTemplate,
        product_context: dict | None = None,
    ) -> str:
        context = product_context or {}
        product_name = str(context.get("product_name") or context.get("name") or "").strip()
        feature = _first_feature(context)
        text = template.text.format(product_name=product_name, feature=feature)
        text = " ".join(text.replace("\r", " ").replace("\n", " ").split())
        if _contains_risky_claim(text):
            raise ValueError(f"Caption template contains a risky unsupported claim: {template.id}")
        return _shorten(text, template.max_chars)

    def _eligible(
        self,
        industry: str,
        intent: str,
        strategy: str,
        product_context: dict | None,
    ) -> list[SilentCaptionTemplate]:
        context = product_context or {}
        has_name = bool(str(context.get("product_name") or context.get("name") or "").strip())
        has_feature = bool(_first_feature(context))
        return [
            template
            for template in self.list_templates(industry=industry, intent=intent, strategy=strategy)
            if (not template.requires_product_name or has_name)
            and (not template.requires_feature or has_feature)
            and (not template.banned_if_no_context or bool(context))
        ]

    def _compatible_candidates(
        self,
        industry: str,
        intent: str,
        strategy: str,
        product_context: dict | None,
    ) -> list[SilentCaptionTemplate]:
        target = _intent(intent)
        compatible_intents = (
            [SilentCaptionIntent.cta]
            if target == SilentCaptionIntent.cta
            else [item for item in SilentCaptionIntent if item != SilentCaptionIntent.cta]
        )
        candidates: list[SilentCaptionTemplate] = []
        for candidate_intent in compatible_intents:
            candidates.extend(self._eligible(industry, candidate_intent.value, strategy, product_context))
        for candidate_intent in compatible_intents:
            candidates.extend(
                self._eligible(
                    SilentCaptionIndustry.general_product.value,
                    candidate_intent.value,
                    strategy,
                    product_context,
                )
            )
        return list({candidate.id: candidate for candidate in candidates}.values())


def list_industries() -> list[dict[str, str]]:
    labels = {
        SilentCaptionIndustry.general_product: "General Product",
        SilentCaptionIndustry.home_goods: "Home Goods",
        SilentCaptionIndustry.kitchen_goods: "Kitchen Goods",
        SilentCaptionIndustry.storage_organization: "Storage / Organization",
        SilentCaptionIndustry.desk_setup: "Desk Setup",
        SilentCaptionIndustry.dorm_goods: "Dorm Goods",
        SilentCaptionIndustry.beauty_goods: "Beauty Goods",
        SilentCaptionIndustry.cleaning_goods: "Cleaning Goods",
    }
    return [{"id": item.value, "name": labels[item]} for item in SilentCaptionIndustry]


def normalize_industry(value: str | None) -> str:
    aliases = {
        "home": "home_goods",
        "home_goods": "home_goods",
        "kitchen": "kitchen_goods",
        "kitchen_goods": "kitchen_goods",
        "storage": "storage_organization",
        "storage_organization": "storage_organization",
        "desk": "desk_setup",
        "desk_setup": "desk_setup",
        "dorm": "dorm_goods",
        "dorm_goods": "dorm_goods",
        "beauty": "beauty_goods",
        "beauty_goods": "beauty_goods",
        "cleaning": "cleaning_goods",
        "cleaning_goods": "cleaning_goods",
        "general": "general_product",
        "general_product": "general_product",
    }
    normalized = "_".join(str(value or "").strip().casefold().replace("/", " ").split())
    return aliases.get(normalized, SilentCaptionIndustry.general_product.value)


def _industry(value: str | None) -> SilentCaptionIndustry:
    return SilentCaptionIndustry(normalize_industry(value))


def _intent(value: str | None) -> SilentCaptionIntent:
    try:
        return SilentCaptionIntent(str(value or "hook").strip().casefold())
    except ValueError:
        return SilentCaptionIntent.hook


def _first_feature(context: dict) -> str:
    features = context.get("features") or []
    if isinstance(features, str):
        features = [line.strip() for line in features.splitlines() if line.strip()]
    if not isinstance(features, list) or not features:
        return ""
    return str(features[0]).strip()


def _contains_risky_claim(text: str) -> bool:
    normalized = text.casefold()
    return any(term in normalized for term in [*RISKY_CLAIM_TERMS, *SENSITIVE_CLAIM_TERMS])


def _shorten(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    words: list[str] = []
    for word in text.split():
        candidate = " ".join([*words, word])
        if len(candidate) > max_chars:
            break
        words.append(word)
    return " ".join(words) or text[:max_chars].rstrip()


def _similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left.casefold(), right.casefold()).ratio()
