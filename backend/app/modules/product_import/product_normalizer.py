from __future__ import annotations

import re
import unicodedata

from app.modules.product_import.product_import_schema import ProductInfoNormalized
from app.schemas.project_schema import ProductSpec


CTA_BY_INDUSTRY = {
    "general_product": "Xem chi tiết sản phẩm ngay",
    "fast_sale_trending": "Xem ưu đãi hôm nay",
    "tech_electronics": "Xem thông tin sản phẩm ngay",
    "beauty_cosmetics": "Xem chi tiết trước khi chọn mua",
    "fashion_accessories": "Xem màu và size phù hợp",
}


class ProductNormalizer:
    def normalize(self, product: ProductInfoNormalized) -> ProductInfoNormalized:
        name = _clean_text(product.name)
        brand = _clean_text(product.brand or "") or None
        features = _dedupe([_clean_bullet(item) for item in product.features], max_items=8)
        specs = _dedupe_specs(product.specs, max_items=12)
        description = _limit_text(_clean_text(product.description), 220)
        if not description and features:
            description = _limit_text(_build_description(name, features), 220)

        cta = _clean_text(product.cta)
        if not cta or cta == "Xem chi tiết sản phẩm ngay":
            cta = CTA_BY_INDUSTRY.get(product.industry_preset_id or "general_product", CTA_BY_INDUSTRY["general_product"])
        cta = _limit_text(cta, 80)

        hashtags = _dedupe([_normalize_hashtag(item) for item in product.hashtag_suggestions], max_items=8)
        warnings = _dedupe([_clean_text(item) for item in product.warnings], max_items=20)
        missing_fields = _dedupe([_clean_text(item) for item in product.missing_fields], max_items=10)

        return product.model_copy(
            update={
                "name": name,
                "brand": brand,
                "description": description,
                "features": features,
                "specs": specs,
                "cta": cta,
                "hashtag_suggestions": hashtags,
                "warnings": warnings,
                "missing_fields": missing_fields,
            }
        )


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).replace("\ufeff", " ").split())


def _clean_bullet(value: str) -> str:
    cleaned = _clean_text(value)
    cleaned = re.sub(r"^[\-\*\u2022\.\+\s]+", "", cleaned).strip()
    return cleaned


def _limit_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    trimmed = value[:limit].rstrip()
    if " " in trimmed:
        trimmed = trimmed.rsplit(" ", 1)[0].rstrip()
    return trimmed


def _dedupe(values: list[str], max_items: int) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        text = _clean_text(value)
        key = text.casefold()
        if not text or key in seen:
            continue
        cleaned.append(text)
        seen.add(key)
        if len(cleaned) >= max_items:
            break
    return cleaned


def _dedupe_specs(values: list[ProductSpec], max_items: int) -> list[ProductSpec]:
    seen: set[str] = set()
    cleaned: list[ProductSpec] = []
    for spec in values:
        name = _clean_bullet(spec.name)
        value = _clean_text(spec.value)
        if not name or not value:
            continue
        key = f"{name.casefold()}={value.casefold()}"
        if key in seen:
            continue
        cleaned.append(ProductSpec(name=name, value=value))
        seen.add(key)
        if len(cleaned) >= max_items:
            break
    return cleaned


def _build_description(name: str, features: list[str]) -> str:
    if not name:
        return ". ".join(features[:2])
    details = ", ".join(features[:3])
    return f"{name} với {details}."


def _normalize_hashtag(value: str) -> str:
    cleaned = _clean_text(value).lower()
    if not cleaned:
        return ""
    normalized = unicodedata.normalize("NFD", cleaned)
    no_accent = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    slug = re.sub(r"[^a-z0-9_]+", "", no_accent.replace("đ", "d"))
    if not slug:
        return ""
    return f"#{slug.lstrip('#')}"
