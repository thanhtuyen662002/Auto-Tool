from __future__ import annotations

import json

from app.modules.industry_presets.industry_registry import get_industry_preset
from app.modules.product_import.product_import_schema import (
    ProductImportResult,
    ProductImportSource,
    ProductInfoNormalized,
    ProductValidationIssue,
    RawProductInput,
)
from app.modules.product_import.product_normalizer import ProductNormalizer
from app.modules.product_import.product_parser import ProductParser
from app.modules.product_import.product_validator import CLAIM_RISK_TERMS, ProductValidator


class ProductImportService:
    def __init__(
        self,
        parser: ProductParser | None = None,
        normalizer: ProductNormalizer | None = None,
        validator: ProductValidator | None = None,
    ) -> None:
        self.parser = parser or ProductParser()
        self.normalizer = normalizer or ProductNormalizer()
        self.validator = validator or ProductValidator()

    def import_product_info(self, raw_input: RawProductInput) -> ProductImportResult:
        raw_preview = _raw_preview(raw_input)
        source = _source_info(raw_input)
        try:
            parsed = self.parser.parse(raw_input)
            normalized = self.normalizer.normalize(parsed)
            industry_id = normalized.industry_preset_id or suggest_industry_preset(normalized)
            industry = get_industry_preset(industry_id)
            with_industry = normalized.model_copy(
                update={
                    "industry_preset_id": industry.id,
                    "hashtag_suggestions": normalized.hashtag_suggestions or industry.hashtag_suggestions,
                }
            )
            normalized = self.normalizer.normalize(with_industry)
            issues = self.validator.validate(normalized)
            warnings = [*normalized.warnings, *[issue.message for issue in issues if issue.severity == "warning"]]
            missing_fields = [issue.field for issue in issues if issue.severity == "error"]
            normalized = normalized.model_copy(
                update={
                    "warnings": _dedupe(warnings),
                    "missing_fields": _dedupe(missing_fields),
                    "confidence_score": _confidence_score(normalized, issues),
                }
            )
            success = not any(issue.severity == "error" for issue in issues)
            return ProductImportResult(
                success=success,
                product=normalized,
                issues=issues,
                source=source,
                raw_preview=raw_preview,
            )
        except Exception as exc:
            return ProductImportResult(
                success=False,
                product=None,
                issues=[
                    ProductValidationIssue(
                        field="input",
                        severity="error",
                        message=f"Không thể import thông tin sản phẩm: {exc}",
                    )
                ],
                source=source,
                raw_preview=raw_preview,
            )


def suggest_industry_preset(product: ProductInfoNormalized) -> str:
    text = " ".join(
        [
            product.name,
            product.brand or "",
            product.description,
            *product.features,
            *(f"{spec.name} {spec.value}" for spec in product.specs),
        ]
    ).casefold()
    keyword_map = {
        "fast_sale_trending": ["deal", "sale", "hot trend", "bán chạy", "ưu đãi"],
        "mom_baby": ["bé", "mẹ", "trẻ em", "bình sữa", "bỉm", "khăn giấy", "đồ chơi trẻ"],
        "tech_electronics": [
            "máy chiếu",
            "tai nghe",
            "bàn phím",
            "chuột",
            "loa",
            "camera",
            "may chieu",
            "dien thoai",
            "den led",
            "do sang",
            "lumens",
            "sạc",
            "cáp",
            "điện thoại",
            "đèn led",
        ],
        "beauty_cosmetics": ["serum", "kem", "son", "phấn", "skincare", "dưỡng", "makeup", "mặt nạ", "toner"],
        "fashion_accessories": ["áo", "quần", "váy", "túi", "giày", "dép", "mũ", "áo chống nắng", "phụ kiện"],
        "home_lifestyle": ["gia dụng", "bếp", "lau nhà", "hút bụi", "kệ", "đèn", "máy xay", "nồi", "chảo"],
        "food_beverage": ["cà phê", "trà", "bánh", "nước", "đồ ăn", "gia vị", "sữa", "thực phẩm"],
    }
    for preset_id, keywords in keyword_map.items():
        if any(keyword in text for keyword in keywords):
            return preset_id
    return "general_product"


def _confidence_score(product: ProductInfoNormalized, issues: list[ProductValidationIssue]) -> float:
    score = 0.0
    if product.name:
        score += 0.25
    if product.brand:
        score += 0.15
    if product.description:
        score += 0.20
    if len(product.features) >= 3:
        score += 0.20
    if product.cta:
        score += 0.10
    if product.industry_preset_id:
        score += 0.10

    text = " ".join([product.name, product.description, *product.features]).casefold()
    if any(term in text for term in CLAIM_RISK_TERMS) or any(issue.field == "claims" for issue in issues):
        score -= 0.15
    if len(product.description) < 25:
        score -= 0.10
    if len(product.features) < 3:
        score -= 0.10
    return max(0.0, min(1.0, round(score, 2)))


def _raw_preview(raw_input: RawProductInput) -> str | None:
    text = raw_input.file_content or raw_input.raw_text
    if not text and raw_input.structured_data:
        text = json.dumps(raw_input.structured_data, ensure_ascii=False)
    if not text and raw_input.file_path:
        text = raw_input.file_path
    if not text and raw_input.source_url:
        text = raw_input.source_url
    if not text:
        return None
    return text[:500]


def _source_info(raw_input: RawProductInput) -> ProductImportSource | None:
    if not raw_input.source_name and not raw_input.source_url:
        return None
    return ProductImportSource(name=raw_input.source_name, url=raw_input.source_url)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        text = " ".join(str(value).strip().split())
        if not text or text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
    return cleaned
