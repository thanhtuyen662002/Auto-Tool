from __future__ import annotations

import re
import unicodedata
from typing import Any


PLACEHOLDER_PRODUCT_NAMES = {
    "auto tool",
    "autotool",
    "demo",
    "douyin",
    "douyin reup",
    "test",
}

GENERIC_PRODUCT_TERMS = {
    "add overlay",
    "auto tool",
    "bgm",
    "dich phu de",
    "dich subtitle",
    "overlay",
    "phu de",
    "render",
    "reup",
    "subtitle",
    "them overlay",
    "tron nhac",
    "tts",
    "voiceover",
    "xu ly video douyin",
}

GENERIC_INDUSTRIES = {"", "auto", "general", "general product", "general_product"}


def sanitize_product_context(product_context: dict | None) -> dict[str, Any] | None:
    """Drop app/demo placeholders so silent mode can follow the video itself."""

    if not product_context:
        return None

    context = dict(product_context)
    if not is_placeholder_product_context(context):
        return context

    cleaned: dict[str, Any] = {}
    industry = _meaningful_industry(context)
    lock_industry = bool(str(context.get("locked_industry") or "").strip())
    if industry:
        cleaned["industry"] = industry
        cleaned["category"] = industry
        if lock_industry:
            cleaned["locked_industry"] = industry

    keywords = [item for item in _clean_list(context.get("locked_product_keywords")) if not _is_generic_text(item)]
    if keywords:
        cleaned["locked_product_keywords"] = keywords

    if cleaned:
        cleaned["product_context_lock_enabled"] = lock_industry
        cleaned["lock_product_context"] = False
        return cleaned
    return None


def has_real_product_context(product_context: dict | None) -> bool:
    context = sanitize_product_context(product_context)
    if not context:
        return False
    values = [
        context.get("product_name"),
        context.get("name"),
        context.get("description"),
        context.get("features"),
        context.get("locked_product_keywords"),
    ]
    for value in values:
        if isinstance(value, list) and any(str(item).strip() for item in value):
            return True
        if isinstance(value, str) and value.strip():
            return True
        if value and not isinstance(value, (str, list)):
            return True
    return False


def is_placeholder_product_context(product_context: dict | None) -> bool:
    if not product_context:
        return False
    if _has_explicit_product_lock(product_context):
        return False

    name = _normalize_text(product_context.get("product_name") or product_context.get("name"))
    name_is_placeholder = not name or name in PLACEHOLDER_PRODUCT_NAMES or "douyin reup" in name
    if not name_is_placeholder:
        return False

    brand = _normalize_text(product_context.get("brand"))
    features = _clean_list(product_context.get("features"))
    description = _normalize_text(product_context.get("description"))

    meaningful_features = [item for item in features if not _is_generic_text(item)]
    meaningful_description = bool(description and not _is_generic_text(description))
    return not brand and not meaningful_features and not meaningful_description


def _has_explicit_product_lock(context: dict) -> bool:
    return bool(
        str(context.get("locked_product_name") or "").strip()
        or bool(context.get("lock_product_context"))
    )


def _meaningful_industry(context: dict) -> str:
    value = str(context.get("locked_industry") or context.get("industry") or context.get("category") or "").strip()
    normalized = _normalize_text(value).replace(" ", "_")
    if normalized in GENERIC_INDUSTRIES:
        return ""
    return value


def _clean_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [line.strip() for line in value.splitlines() if line.strip()]
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _is_generic_text(value: Any) -> bool:
    text = _normalize_text(value)
    if not text:
        return True
    if text in {"demo", "test", "xem"}:
        return True
    return any(term in text for term in GENERIC_PRODUCT_TERMS)


def _normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().casefold()
    return " ".join(text.split())
