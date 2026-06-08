from __future__ import annotations

import csv
import json
import re
from io import StringIO
from pathlib import Path
from typing import Any

from app.modules.product_import.product_import_schema import ProductInfoNormalized, RawProductInput
from app.schemas.project_schema import ProductSpec


class ProductParser:
    def parse(self, raw_input: RawProductInput) -> ProductInfoNormalized:
        if raw_input.input_type == "shopee_extension":
            return self._parse_shopee_extension(raw_input)

        text = _read_input_text(raw_input)
        if raw_input.input_type == "json":
            return self._parse_json(text)
        if raw_input.input_type == "csv":
            return self._parse_csv(text)
        return self._parse_text(text)

    def _parse_json(self, text: str) -> ProductInfoNormalized:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"File JSON không hợp lệ: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("JSON import phải là object sản phẩm.")

        name = _first_alias(payload, "name", "product_name", "ten_san_pham", "title")
        brand = _first_alias(payload, "brand", "brand_name", "thuong_hieu")
        description = _first_alias(payload, "description", "desc", "mo_ta")
        features = _list_alias(payload, "features", "benefits", "highlights", "diem_noi_bat")
        specs = _specs_from_value(_first_existing(payload, "specs", "specifications", "thong_so"))
        cta = _first_alias(payload, "cta", "call_to_action") or "Xem chi tiết sản phẩm ngay"
        return ProductInfoNormalized(
            name=name or "",
            brand=brand,
            description=description or "",
            features=features,
            specs=specs,
            cta=cta,
        )

    def _parse_csv(self, text: str) -> ProductInfoNormalized:
        reader = csv.DictReader(StringIO(text))
        rows = list(reader)
        if not rows:
            raise ValueError("CSV không có dữ liệu sản phẩm.")
        row = {str(key or "").strip(): value for key, value in rows[0].items()}
        result = self._parse_json(json.dumps(row, ensure_ascii=False))
        if len(rows) > 1:
            result = result.model_copy(
                update={
                    "warnings": [
                        *result.warnings,
                        "CSV có nhiều dòng, hiện tại chỉ import dòng đầu tiên.",
                    ]
                }
        )
        return result

    def _parse_shopee_extension(self, raw_input: RawProductInput) -> ProductInfoNormalized:
        data = raw_input.structured_data or {}
        if not isinstance(data, dict):
            raise ValueError("structured_data must be an object for shopee_extension input.")

        fallback = _parse_optional_text(raw_input, self)
        shopee = data.get("shopee") if isinstance(data.get("shopee"), dict) else {}
        shop = data.get("shop") if isinstance(data.get("shop"), dict) else {}

        name = _clean_value(data.get("name")) or _clean_value(shopee.get("name")) or fallback.name
        brand = (
            _clean_value(data.get("brand"))
            or _clean_value(shopee.get("brand"))
            or _brand_from_specs(data)
            or _brand_from_specs(shopee)
            or fallback.brand
        )
        description_text = (
            _clean_value(data.get("description"))
            or _clean_value(shopee.get("description"))
            or fallback.description
        )
        features = _limit_texts(_list_alias(data, "features", "benefits", "highlights"), limit=8, max_length=90)
        if not features:
            features = _limit_texts(_features_from_shopee_data(data, shopee), limit=8, max_length=90)
        if not features:
            features = _limit_texts(fallback.features, limit=8, max_length=90)

        specs = _specs_from_value(_first_existing(data, "specs", "specifications", "thong_so"))
        if not specs:
            specs = _specs_from_value(_first_existing(shopee, "specs", "specifications", "thong_so"))
        specs = _merge_specs(
            specs,
            _commerce_specs_from_shopee(data, shopee, shop),
            fallback.specs if not specs else [],
        )

        cta = _clean_value(data.get("cta")) or fallback.cta or ProductInfoNormalized().cta
        description = _build_shopee_description(name, description_text, features)
        warnings = _shopee_warnings(data, shopee, name, brand, specs, raw_input.source_url)
        warnings = _dedupe_texts([*warnings, *fallback.warnings])

        return ProductInfoNormalized(
            name=name or "",
            brand=brand,
            description=description,
            features=features,
            specs=specs,
            cta=cta,
            warnings=warnings,
        )

    def _parse_text(self, text: str) -> ProductInfoNormalized:
        lines = [_clean_line(line) for line in text.splitlines()]
        lines = [line for line in lines if line]
        if not lines:
            return ProductInfoNormalized()

        name = lines[0]
        brand: str | None = None
        features: list[str] = []
        specs: list[ProductSpec] = []
        description_candidates: list[str] = []
        cta = "Xem chi tiết sản phẩm ngay"

        for line in lines[1:]:
            key, value = _split_key_value(line)
            normalized_key = _normalize_key(key)
            if normalized_key in {"thuong hieu", "brand", "brand name"} and value:
                brand = value
                continue
            if normalized_key in {"cta", "call to action"} and value:
                cta = value
                continue
            if normalized_key in {"mo ta", "description", "desc"} and value:
                description_candidates.append(value)
                continue
            if normalized_key in {"tinh nang", "diem noi bat", "feature", "features", "benefit", "benefits"} and value:
                features.extend(_split_multi_value(value))
                continue
            if key and value and _looks_like_spec(line):
                specs.append(ProductSpec(name=key, value=value))
                continue
            if _looks_like_spec(line):
                spec = _spec_from_line(line)
                if spec is not None:
                    specs.append(spec)
                    continue
            features.append(line)

        if not description_candidates:
            description_candidates = features[:2]
        description = _build_description(name, description_candidates)
        return ProductInfoNormalized(
            name=name,
            brand=brand,
            description=description,
            features=features,
            specs=specs,
            cta=cta,
        )


def _read_input_text(raw_input: RawProductInput) -> str:
    if raw_input.file_content:
        return raw_input.file_content
    if raw_input.raw_text:
        return raw_input.raw_text
    if raw_input.file_path:
        path = Path(raw_input.file_path).expanduser()
        if not path.exists() or not path.is_file():
            raise ValueError(f"Không tìm thấy file import: {path}")
        return path.read_text(encoding="utf-8")
    raise ValueError("Cần cung cấp raw_text, file_content hoặc file_path để import sản phẩm.")


def _parse_optional_text(raw_input: RawProductInput, parser: ProductParser) -> ProductInfoNormalized:
    if not raw_input.file_content and not raw_input.raw_text and not raw_input.file_path:
        return ProductInfoNormalized()
    return parser._parse_text(_read_input_text(raw_input))


def _clean_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    cleaned = " ".join(str(value).strip().split())
    return cleaned or None


def _limit_texts(values: list[str], limit: int, max_length: int) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean_line(value)
        if not text:
            continue
        if len(text) > max_length:
            text = text[: max_length - 3].rstrip() + "..."
        key = text.casefold()
        if key in seen:
            continue
        cleaned.append(text)
        seen.add(key)
        if len(cleaned) >= limit:
            break
    return cleaned


def _features_from_shopee_data(data: dict[str, Any], shopee: dict[str, Any]) -> list[str]:
    features: list[str] = []
    for label, value in [
        ("Gia", _first_existing(data, "price", "gia") or _first_existing(shopee, "price", "gia")),
        ("Giam gia", _first_existing(data, "discount") or _first_existing(shopee, "discount")),
        ("Danh gia", _first_existing(shopee, "rating")),
        ("Da ban", _first_existing(shopee, "soldCount", "sold_count")),
    ]:
        text = _clean_value(value)
        if text:
            features.append(f"{label}: {text}")

    variations = data.get("variations") or shopee.get("variations")
    if isinstance(variations, list):
        for variation in variations:
            if not isinstance(variation, dict):
                continue
            name = _clean_value(variation.get("name"))
            options = variation.get("options")
            if name and isinstance(options, list):
                option_text = ", ".join(_limit_texts([str(item) for item in options], limit=4, max_length=30))
                if option_text:
                    features.append(f"{name}: {option_text}")

    description = _clean_value(data.get("description")) or _clean_value(shopee.get("description"))
    if description:
        features.extend(_description_feature_candidates(description))
    return features


def _description_feature_candidates(description: str) -> list[str]:
    candidates: list[str] = []
    for line in re.split(r"[\n\r;|]+", description):
        text = _clean_line(line)
        if not text or len(text) < 8:
            continue
        if len(text) <= 90 or re.match(r"^[-*+•]", line.strip()):
            candidates.append(text)
        if len(candidates) >= 6:
            break
    return candidates


def _brand_from_specs(payload: dict[str, Any]) -> str | None:
    specs = _first_existing(payload, "specs", "specifications", "thong_so")
    if not isinstance(specs, dict):
        return None
    for key, value in specs.items():
        normalized_key = _normalize_key(str(key))
        if normalized_key in {"brand", "thuong hieu", "brand name"}:
            return _clean_value(value)
    return None


def _commerce_specs_from_shopee(
    data: dict[str, Any],
    shopee: dict[str, Any],
    shop: dict[str, Any],
) -> list[ProductSpec]:
    specs: list[ProductSpec] = []
    for name, value in [
        ("Gia", _first_existing(data, "price", "gia") or _first_existing(shopee, "price", "gia")),
        ("Gia goc", _first_existing(data, "originalPrice") or _first_existing(shopee, "originalPrice")),
        ("Giam gia", _first_existing(data, "discount") or _first_existing(shopee, "discount")),
        ("Danh gia", _first_existing(shopee, "rating")),
        ("Da ban", _first_existing(shopee, "soldCount", "sold_count")),
        ("Luot danh gia", _first_existing(shopee, "reviewCount", "review_count")),
        ("Shop", _first_existing(shop, "name") or _first_existing(shopee, "shopName", "shop_name")),
        ("Dia chi shop", _first_existing(shop, "location") or _first_existing(shopee, "shopLocation", "shop_location")),
    ]:
        text = _clean_value(value)
        if text:
            specs.append(ProductSpec(name=name, value=text))
    return specs


def _merge_specs(*groups: list[ProductSpec]) -> list[ProductSpec]:
    merged: list[ProductSpec] = []
    seen: set[tuple[str, str]] = set()
    for group in groups:
        for spec in group:
            key = (_normalize_key(spec.name), spec.value.casefold())
            if key in seen:
                continue
            merged.append(spec)
            seen.add(key)
            if len(merged) >= 15:
                return merged
    return merged


def _build_shopee_description(name: str | None, description: str | None, features: list[str]) -> str:
    parts = [part for part in [name, description] if part]
    if not description and features:
        parts.append(", ".join(features[:3]))
    if not parts:
        return ""
    text = ". ".join(parts)
    return text[:700].rstrip()


def _shopee_warnings(
    data: dict[str, Any],
    shopee: dict[str, Any],
    name: str | None,
    brand: str | None,
    specs: list[ProductSpec],
    source_url: str | None,
) -> list[str]:
    warnings = [
        *_warning_list(data.get("warnings")),
        *_warning_list(shopee.get("warnings")),
    ]
    if not name:
        warnings.append("Shopee payload does not include product name.")
    if not brand:
        warnings.append("Shopee payload does not include brand.")
    if not specs:
        warnings.append("Shopee payload does not include specifications.")
    if not source_url:
        warnings.append("Shopee payload does not include source_url.")
    return _dedupe_texts(warnings)


def _warning_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [_clean_value(item) or "" for item in value]
    return [_clean_value(value) or ""]


def _dedupe_texts(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean_value(value)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        cleaned.append(text)
        seen.add(key)
    return cleaned


def _clean_line(value: str) -> str:
    cleaned = str(value).replace("\ufeff", " ").strip()
    cleaned = re.sub(r"^[\-\*\u2022\.\+\s]+", "", cleaned)
    return " ".join(cleaned.split())


def _split_key_value(line: str) -> tuple[str, str]:
    for sep in (":", "：", "-"):
        if sep in line:
            left, right = line.split(sep, 1)
            if left.strip() and right.strip():
                return left.strip(), right.strip()
    return "", ""


def _normalize_key(value: str) -> str:
    replacements = {
        "à": "a",
        "á": "a",
        "ả": "a",
        "ã": "a",
        "ạ": "a",
        "ă": "a",
        "ằ": "a",
        "ắ": "a",
        "ẳ": "a",
        "ẵ": "a",
        "ặ": "a",
        "â": "a",
        "ầ": "a",
        "ấ": "a",
        "ẩ": "a",
        "ẫ": "a",
        "ậ": "a",
        "è": "e",
        "é": "e",
        "ẻ": "e",
        "ẽ": "e",
        "ẹ": "e",
        "ê": "e",
        "ề": "e",
        "ế": "e",
        "ể": "e",
        "ễ": "e",
        "ệ": "e",
        "ì": "i",
        "í": "i",
        "ỉ": "i",
        "ĩ": "i",
        "ị": "i",
        "ò": "o",
        "ó": "o",
        "ỏ": "o",
        "õ": "o",
        "ọ": "o",
        "ô": "o",
        "ồ": "o",
        "ố": "o",
        "ổ": "o",
        "ỗ": "o",
        "ộ": "o",
        "ơ": "o",
        "ờ": "o",
        "ớ": "o",
        "ở": "o",
        "ỡ": "o",
        "ợ": "o",
        "ù": "u",
        "ú": "u",
        "ủ": "u",
        "ũ": "u",
        "ụ": "u",
        "ư": "u",
        "ừ": "u",
        "ứ": "u",
        "ử": "u",
        "ữ": "u",
        "ự": "u",
        "ỳ": "y",
        "ý": "y",
        "ỷ": "y",
        "ỹ": "y",
        "ỵ": "y",
        "đ": "d",
    }
    cleaned = value.casefold()
    return "".join(replacements.get(ch, ch) for ch in cleaned)


def _looks_like_spec(line: str) -> bool:
    lowered = line.casefold()
    spec_keywords = [
        "độ sáng",
        "dung lượng",
        "công suất",
        "kích thước",
        "trọng lượng",
        "chất liệu",
        "hệ điều hành",
        "điện áp",
        "pin",
        "watt",
        "lumens",
        "mah",
        "gb",
        "cm",
        "mm",
        "kg",
        "hz",
    ]
    if any(keyword in lowered for keyword in spec_keywords):
        return True
    return bool(re.search(r"\b\d+([.,]\d+)?\s?(w|hz|mah|gb|cm|mm|kg|g|ml|l|inch|lumens)\b", lowered))


def _spec_from_line(line: str) -> ProductSpec | None:
    key, value = _split_key_value(line)
    if key and value:
        return ProductSpec(name=key, value=value)
    match = re.search(r"(.{2,40}?)\s+(\d[\w\s.,/%+-]*$)", line)
    if not match:
        return None
    return ProductSpec(name=match.group(1).strip(), value=match.group(2).strip())


def _first_alias(payload: dict[str, Any], *aliases: str) -> str | None:
    value = _first_existing(payload, *aliases)
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip() or None


def _first_existing(payload: dict[str, Any], *aliases: str) -> Any:
    normalized = {_normalize_key(key).replace("_", " "): value for key, value in payload.items()}
    for alias in aliases:
        if alias in payload:
            return payload[alias]
        normalized_alias = _normalize_key(alias).replace("_", " ")
        if normalized_alias in normalized:
            return normalized[normalized_alias]
    return None


def _list_alias(payload: dict[str, Any], *aliases: str) -> list[str]:
    value = _first_existing(payload, *aliases)
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, dict):
        return [f"{key}: {val}" for key, val in value.items() if str(val).strip()]
    return _split_multi_value(str(value))


def _split_multi_value(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[;\n|]+", value) if item.strip()]


def _specs_from_value(value: Any) -> list[ProductSpec]:
    if value is None:
        return []
    specs: list[ProductSpec] = []
    if isinstance(value, dict):
        for key, val in value.items():
            if str(key).strip() and str(val).strip():
                specs.append(ProductSpec(name=str(key), value=str(val)))
        return specs
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                name = _first_alias(item, "name", "key", "label")
                val = _first_alias(item, "value", "val")
                if name and val:
                    specs.append(ProductSpec(name=name, value=val))
            elif isinstance(item, str):
                spec = _spec_from_line(item)
                if spec is not None:
                    specs.append(spec)
        return specs
    for part in _split_multi_value(str(value)):
        spec = _spec_from_line(part)
        if spec is not None:
            specs.append(spec)
    return specs


def _build_description(name: str, candidates: list[str]) -> str:
    parts = [item for item in candidates if item and item != name]
    if not parts:
        return name
    return f"{name} với {', '.join(parts[:3])}."
