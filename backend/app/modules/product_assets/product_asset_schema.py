from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductAssetType(str, Enum):
    image = "image"
    video = "video"
    thumbnail = "thumbnail"
    unknown = "unknown"


class ProductAssetRole(str, Enum):
    main_product = "main_product"
    reference = "reference"
    poster = "poster"
    thumbnail = "thumbnail"
    description = "description"
    variation = "variation"
    unused = "unused"


class ProductAssetStatus(str, Enum):
    pending = "pending"
    downloaded = "downloaded"
    failed = "failed"
    skipped = "skipped"


class ProductAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    project_id: str | None = None
    draft_id: str | None = None

    source_name: str | None = None
    source_url: str | None = None
    original_url: str | None = None

    asset_type: ProductAssetType = ProductAssetType.image
    role: ProductAssetRole = ProductAssetRole.reference
    status: ProductAssetStatus = ProductAssetStatus.pending

    filename: str | None = None
    local_path: str | None = None

    width: int | None = None
    height: int | None = None
    file_size: int | None = None
    mime_type: str | None = None

    quality_score: float | None = None
    is_selected: bool = False
    user_note: str | None = None

    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    created_at: str
    updated_at: str

    @field_validator("source_name", "source_url", "original_url", "filename", "local_path", "user_note")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(str(value).strip().split())
        return cleaned or None

    @field_validator("warnings", "errors")
    @classmethod
    def clean_message_list(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            text = " ".join(str(item).strip().split())
            if not text or text in seen:
                continue
            cleaned.append(text)
            seen.add(text)
        return cleaned


class ImportAssetsFromDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: str | None = None
    project_id: str | None = None
    selected_asset_urls: list[str] | None = None
    download_selected: bool = True

    @field_validator("selected_asset_urls")
    @classmethod
    def clean_urls(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            url = str(item).strip()
            if not url or url in seen:
                continue
            cleaned.append(url)
            seen.add(url)
        return cleaned


class UpdateProductAssetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: ProductAssetRole | None = None
    is_selected: bool | None = None
    user_note: str | None = None


class AttachDraftAssetsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_asset_ids: list[str] | None = None


class ProductAssetListResponse(BaseModel):
    items: list[ProductAsset]


class ProductAssetsImportResponse(BaseModel):
    success: bool
    items: list[ProductAsset]


class AttachDraftAssetsResponse(BaseModel):
    success: bool
    project_id: str
    attached_count: int
    items: list[ProductAsset]
