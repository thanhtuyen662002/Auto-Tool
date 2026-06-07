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
