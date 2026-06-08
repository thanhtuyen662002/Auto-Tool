from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.product_import.product_import_schema import ProductInfoNormalized, ProductValidationIssue
from app.schemas.project_schema import ProductInfo, ProjectConfig


class ProductDraftStatus(str, Enum):
    new = "new"
    reviewed = "reviewed"
    applied = "applied"
    archived = "archived"


class ProductDraftSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_name: str | None = None
    source_url: str | None = None
    imported_at: str
    imported_by: str = "chrome_extension"

    @field_validator("source_name", "source_url", "imported_by")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.strip().split())
        return cleaned or None


class ProductDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    status: ProductDraftStatus = ProductDraftStatus.new
    source: ProductDraftSource
    raw_input: dict[str, Any] | None = None
    raw_text: str | None = None
    structured_data: dict[str, Any] | None = None
    extractor_debug: dict[str, Any] | None = None
    normalized_product: ProductInfoNormalized | None = None
    validation_issues: list[ProductValidationIssue] = Field(default_factory=list)
    industry_preset_id: str | None = None
    confidence_score: float = 0.0
    user_note: str | None = None
    created_at: str
    updated_at: str

    @field_validator("title", "industry_preset_id", "user_note")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.strip().split())
        return cleaned or None


class CreateProductDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_type: str
    source_name: str | None = None
    source_url: str | None = None
    raw_text: str | None = None
    file_path: str | None = None
    file_content: str | None = None
    structured_data: dict[str, Any] | None = None
    extractor_debug: dict[str, Any] | None = None
    save_to_inbox: bool = True


class UpdateProductDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normalized_product: ProductInfoNormalized | None = None
    status: ProductDraftStatus | None = None
    user_note: str | None = None


class ProductDraftListResponse(BaseModel):
    items: list[ProductDraft]
    total: int


class ProductDraftSummary(BaseModel):
    id: str
    title: str
    status: ProductDraftStatus
    confidence_score: float = 0.0


class ProductDraftApplyResponse(BaseModel):
    success: bool
    project_id: str
    draft_id: str
    project_product: ProductInfo
    industry_preset_id: str | None = None
    updated_config: ProjectConfig | None = None


class CreateProjectFromDraftRenderSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_count: int = Field(default=3, gt=0)
    duration: float = Field(default=12, gt=0)


class CreateProjectFromDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_name: str
    source_folder: str
    output_folder: str
    render: CreateProjectFromDraftRenderSettings = Field(default_factory=CreateProjectFromDraftRenderSettings)


class CreateProjectFromDraftResponse(BaseModel):
    success: bool
    project_id: str
    draft_id: str
    updated_config: ProjectConfig | None = None


class DeleteProductDraftResponse(BaseModel):
    success: bool


class ClearArchivedDraftsResponse(BaseModel):
    success: bool
    deleted_count: int


class ProjectListItem(BaseModel):
    id: str
    project_name: str
    created_at: str


class ProjectListResponse(BaseModel):
    items: list[ProjectListItem]
