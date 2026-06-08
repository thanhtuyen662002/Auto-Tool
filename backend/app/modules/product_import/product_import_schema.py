from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.project_schema import ProductInfo, ProductSpec


class RawProductInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_type: Literal["manual", "text", "json", "txt", "csv", "shopee_extension"]
    raw_text: str | None = None
    file_path: str | None = None
    file_content: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    structured_data: dict[str, Any] | None = None

    @field_validator("raw_text", "file_path", "file_content", "source_name", "source_url")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ProductInfoNormalized(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = ""
    brand: str | None = None
    description: str = ""
    features: list[str] = Field(default_factory=list)
    specs: list[ProductSpec] = Field(default_factory=list)
    cta: str = "Xem chi tiết sản phẩm ngay"
    industry_preset_id: str | None = None
    hashtag_suggestions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    confidence_score: float = 0.0

    @field_validator("name", "brand", "description", "cta", "industry_preset_id")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.strip().split())
        return cleaned or None

    @field_validator("features", "hashtag_suggestions", "warnings", "missing_fields")
    @classmethod
    def clean_text_list(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in value:
            text = " ".join(str(item).strip().split())
            if not text or text in seen:
                continue
            cleaned.append(text)
            seen.add(text)
        return cleaned


class ProductValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    severity: Literal["info", "warning", "error"]
    message: str
    suggestion: str | None = None


class ProductImportSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    url: str | None = None


class ProductImportDraftSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    status: str
    confidence_score: float = 0.0


class ProductImportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    product: ProductInfoNormalized | None = None
    issues: list[ProductValidationIssue] = Field(default_factory=list)
    source: ProductImportSource | None = None
    draft: ProductImportDraftSummary | None = None
    import_inbox_url: str | None = None
    raw_preview: str | None = None
    error: str | None = None


def to_project_product_info(normalized: ProductInfoNormalized) -> ProductInfo:
    return ProductInfo(
        name=normalized.name,
        brand=normalized.brand or "",
        description=normalized.description,
        features=normalized.features,
        specs=normalized.specs,
        cta=normalized.cta,
        validation_warnings=normalized.warnings,
        hashtag_suggestions=normalized.hashtag_suggestions,
    )
