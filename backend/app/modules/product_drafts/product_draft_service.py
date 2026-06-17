from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from app import database
from app.modules.industry_presets.industry_preset_service import IndustryPresetService
from app.modules.industry_presets.industry_registry import get_industry_preset
from app.modules.industry_presets.industry_schema import IndustrySettings
from app.modules.product_drafts.product_draft_repository import ProductDraftRepository
from app.modules.product_drafts.product_draft_schema import (
    CreateProjectFromDraftRequest,
    CreateProjectFromDraftResponse,
    CreateProductDraftRequest,
    ProductDraft,
    ProductDraftApplyResponse,
    ProductDraftListResponse,
    ProductDraftSource,
    ProductDraftStatus,
    UpdateProductDraftRequest,
)
from app.modules.product_import import ProductImportService, RawProductInput, suggest_industry_preset, to_project_product_info
from app.modules.product_import.product_import_schema import ProductInfoNormalized, ProductValidationIssue
from app.modules.product_import.product_normalizer import ProductNormalizer
from app.modules.product_import.product_validator import ProductValidator
from app.schemas.project_schema import (
    AISettings,
    CacheSettings,
    CropSafetySettings,
    EffectSettings,
    MusicSettings,
    ProductInfo,
    ProjectConfig,
    RenderSettings,
    SourceMediaSettings,
)


class ProductDraftService:
    def __init__(
        self,
        repository: ProductDraftRepository | None = None,
        import_service: ProductImportService | None = None,
    ) -> None:
        self.repository = repository or ProductDraftRepository()
        self.import_service = import_service or ProductImportService()

    def create_from_import_request(self, request: CreateProductDraftRequest) -> ProductDraft:
        raw_input_payload = request.model_dump(mode="json", exclude={"save_to_inbox", "extractor_debug"})
        raw_input = RawProductInput.model_validate(raw_input_payload)
        result = self.import_service.import_product_info(raw_input)
        validation_issues = _with_extension_payload_issues(request, result.issues)
        now = _now()
        product = result.product
        title = _draft_title(product, request.structured_data)
        draft = ProductDraft(
            id=str(uuid.uuid4()),
            title=title,
            status=ProductDraftStatus.new,
            source=ProductDraftSource(
                source_name=request.source_name,
                source_url=request.source_url,
                imported_at=now,
                imported_by=_imported_by(request.source_name),
            ),
            raw_input=raw_input_payload,
            raw_text=request.raw_text or request.file_content,
            structured_data=request.structured_data,
            extractor_debug=request.extractor_debug,
            normalized_product=product,
            validation_issues=validation_issues,
            industry_preset_id=product.industry_preset_id if product else None,
            confidence_score=product.confidence_score if product else 0.0,
            created_at=now,
            updated_at=now,
        )
        return self.repository.create(draft)

    def list_drafts(
        self,
        status: str | None = None,
        source_name: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ProductDraftListResponse:
        if status:
            ProductDraftStatus(status)
        items, total = self.repository.list(status=status, source_name=source_name, limit=limit, offset=offset)
        return ProductDraftListResponse(items=items, total=total)

    def get_draft(self, draft_id: str) -> ProductDraft:
        draft = self.repository.get(draft_id)
        if draft is None:
            raise LookupError(f"Product draft not found: {draft_id}")
        return draft

    def update_draft(self, draft_id: str, request: UpdateProductDraftRequest) -> ProductDraft:
        self.get_draft(draft_id)
        updates: dict[str, Any] = {}
        if request.normalized_product is not None:
            normalized = ProductNormalizer().normalize(request.normalized_product)
            issues = ProductValidator().validate(normalized)
            updates.update(
                {
                    "title": _draft_title(normalized, None),
                    "normalized_product_json": normalized.model_dump(mode="json"),
                    "validation_issues_json": [issue.model_dump(mode="json") for issue in issues],
                    "industry_preset_id": normalized.industry_preset_id,
                    "confidence_score": normalized.confidence_score,
                }
            )
        if request.status is not None:
            updates["status"] = request.status.value
        if request.user_note is not None:
            updates["user_note"] = request.user_note
        updated = self.repository.update(draft_id, updates)
        if updated is None:
            raise LookupError(f"Product draft not found: {draft_id}")
        return updated

    def archive_draft(self, draft_id: str) -> ProductDraft:
        updated = self.repository.update(draft_id, {"status": ProductDraftStatus.archived.value})
        if updated is None:
            raise LookupError(f"Product draft not found: {draft_id}")
        return updated

    def delete_draft(self, draft_id: str) -> bool:
        return self.repository.delete(draft_id)

    def clear_archived(self) -> int:
        return self.repository.clear_archived()

    def apply_to_project(self, draft_id: str, project_id: str) -> ProductDraftApplyResponse:
        draft = self.get_draft(draft_id)
        product = _prepared_product(_require_product(draft))
        project = database.get_project(project_id)
        if not project:
            raise LookupError(f"Project not found: {project_id}")

        config = ProjectConfig.model_validate(project["config"])
        updated_config = _config_with_product(config, product)
        updated = database.update_project_config(project_id, updated_config.model_dump(mode="json"))
        if not updated:
            raise LookupError(f"Project not found: {project_id}")

        self.repository.update(draft_id, {"status": ProductDraftStatus.applied.value})
        return ProductDraftApplyResponse(
            success=True,
            project_id=project_id,
            draft_id=draft_id,
            project_product=updated_config.product,
            industry_preset_id=updated_config.industry.preset_id if updated_config.industry else product.industry_preset_id,
            updated_config=updated_config,
        )

    def create_project_from_draft(
        self,
        draft_id: str,
        request: CreateProjectFromDraftRequest,
    ) -> CreateProjectFromDraftResponse:
        draft = self.get_draft(draft_id)
        product = _prepared_product(_require_product(draft))
        config = _default_project_config_from_draft(product, request)
        config = _config_with_product(config, product)
        project_id = str(uuid.uuid4())
        database.create_project(project_id, config.model_dump(mode="json"))
        if request.attach_selected_assets:
            from app.modules.product_assets import ProductAssetService

            ProductAssetService().attach_draft_assets_to_project(
                draft_id,
                project_id,
                selected_asset_ids=request.selected_asset_ids,
            )
            project = database.get_project(project_id)
            if project:
                config = ProjectConfig.model_validate(project["config"])
        self.repository.update(draft_id, {"status": ProductDraftStatus.applied.value})
        return CreateProjectFromDraftResponse(
            success=True,
            project_id=project_id,
            draft_id=draft_id,
            updated_config=config,
        )


def _with_extension_payload_issues(
    request: CreateProductDraftRequest,
    issues: list[ProductValidationIssue],
) -> list[ProductValidationIssue]:
    if request.input_type != "shopee_extension":
        return issues
    structured_name = ""
    if request.structured_data:
        structured_name = str(request.structured_data.get("name") or "").strip()
    if structured_name:
        return issues
    if any(issue.field == "name" and issue.severity == "error" for issue in issues):
        return issues
    return [
        ProductValidationIssue(
            field="name",
            severity="error",
            message="Shopee Extension payload is missing product name.",
            suggestion="Extract again or fill the product name before sending to Auto Tool.",
        ),
        *issues,
    ]


def _prepared_product(product: ProductInfoNormalized) -> ProductInfoNormalized:
    normalized = ProductNormalizer().normalize(product)
    industry_id = normalized.industry_preset_id or suggest_industry_preset(normalized)
    industry = get_industry_preset(industry_id)
    normalized = ProductNormalizer().normalize(
        normalized.model_copy(
            update={
                "industry_preset_id": industry.id,
                "hashtag_suggestions": normalized.hashtag_suggestions or industry.hashtag_suggestions,
            }
        )
    )
    issues = ProductValidator().validate(normalized)
    errors = [issue for issue in issues if issue.severity == "error"]
    if errors:
        raise ValueError("; ".join(issue.message for issue in errors))
    warnings = [*normalized.warnings, *[issue.message for issue in issues if issue.severity == "warning"]]
    return normalized.model_copy(update={"warnings": _dedupe(warnings)})


def _config_with_product(config: ProjectConfig, product: ProductInfoNormalized) -> ProjectConfig:
    product_info = to_project_product_info(product)
    industry_id = product.industry_preset_id or "general_product"
    updated = config.model_copy(
        update={
            "product": product_info,
            "industry": IndustrySettings(preset_id=industry_id),
        }
    )
    return IndustryPresetService().apply_preset_to_config(updated, industry_id)


def _default_project_config_from_draft(
    product: ProductInfoNormalized,
    request: CreateProjectFromDraftRequest,
) -> ProjectConfig:
    return ProjectConfig(
        project_name=request.project_name or _slugify(product.name),
        source_folder=request.source_folder,
        output_folder=request.output_folder,
        product=_product_info_placeholder(product),
        render=RenderSettings(
            output_count=request.render.output_count,
            duration=request.render.duration,
            aspect_ratio="9:16",
            resolution="1080x1920",
            fps=30,
        ),
        effects=EffectSettings(
            cut_intensity=70,
            speed_variation=30,
            grain=15,
            zoom_motion=25,
            overlay_height=33,
            subtitle_size=84,
        ),
        ai=AISettings(
            text_model="gemini-3.1-flash-lite",
            tone="friendly_reviewer",
            language="vi",
            gemini_api_keys=[],
        ),
        music=MusicSettings(
            enabled=True,
            source_folder="examples/music",
            volume=0.18,
            fade_in=0.5,
            fade_out=0.8,
            duck_under_voice=False,
        ),
        cache=CacheSettings(),
        crop_safety=CropSafetySettings(),
        source_media=SourceMediaSettings(),
    )


def _product_info_placeholder(product: ProductInfoNormalized) -> ProductInfo:
    return ProductInfo(
        name=product.name or "Untitled product",
        brand=product.brand or "",
        description=product.description or product.name or "Draft product description",
        features=product.features or [product.name or "Draft product"],
        specs=product.specs,
        cta=product.cta or "Xem chi tiet san pham ngay",
        validation_warnings=product.warnings,
        hashtag_suggestions=product.hashtag_suggestions,
    )


def _require_product(draft: ProductDraft) -> ProductInfoNormalized:
    if draft.normalized_product is None:
        raise ValueError("Product draft does not have normalized product info.")
    return draft.normalized_product


def _draft_title(product: ProductInfoNormalized | None, structured_data: dict[str, Any] | None) -> str:
    if product and product.name:
        return product.name
    if structured_data:
        name = structured_data.get("name")
        if isinstance(name, str) and name.strip():
            return " ".join(name.strip().split())
    return "Untitled product draft"


def _imported_by(source_name: str | None) -> str:
    return "chrome_extension" if (source_name or "").strip().casefold() == "shopee" else "manual"


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized or "product-draft"


def _dedupe(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = " ".join(str(value).strip().split())
        if not text or text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
    return cleaned


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()
