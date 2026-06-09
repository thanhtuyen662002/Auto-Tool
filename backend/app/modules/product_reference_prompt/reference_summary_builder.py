from __future__ import annotations

from pydantic import ValidationError

from app import database
from app.modules.content_safety.safety_guard_service import SafetyGuardService
from app.modules.industry_presets.industry_registry import get_industry_preset
from app.modules.product_assets.product_asset_repository import ProductAssetRepository
from app.modules.product_assets.product_asset_schema import ProductAsset, ProductAssetRole, ProductAssetStatus
from app.modules.product_reference_prompt.reference_schema import ProductReferenceAsset, ProductReferenceSummary
from app.modules.timeline_templates.template_registry import get_timeline_template
from app.modules.visual_style.style_registry import get_visual_style_preset
from app.schemas.project_schema import ProductInfo, ProjectConfig


DEFAULT_FORBIDDEN_CLAIMS = [
    'Không nói "tốt nhất", "số 1", "100% hiệu quả" nếu không có chứng cứ được cung cấp.',
    "Không thêm thông số kỹ thuật chưa được cung cấp.",
    "Không claim y tế, sức khỏe hoặc làm đẹp nếu product info không có bằng chứng rõ ràng.",
    "Không nói sản phẩm có tính năng chưa được cung cấp.",
    "Không tự thêm logo, chứng nhận, quà tặng hoặc khuyến mãi nếu dữ liệu không có.",
]


class ProductReferenceSummaryBuilder:
    def __init__(
        self,
        asset_repository: ProductAssetRepository | None = None,
        safety_guard: SafetyGuardService | None = None,
    ) -> None:
        self.asset_repository = asset_repository or ProductAssetRepository()
        self.safety_guard = safety_guard or SafetyGuardService()

    def build_summary(self, project_id: str) -> ProductReferenceSummary:
        config = _load_project_config(project_id)
        product = config.product
        if not product.name.strip():
            raise ValueError("Product name is required before generating a prompt pack.")

        reference_assets = self._reference_assets(project_id, config)
        main_asset_id = _main_asset_id(config, reference_assets)
        warnings = self._warnings(config, reference_assets, main_asset_id)
        safety_result = self.safety_guard.check_before_render(config)

        forbidden_claims = [
            *DEFAULT_FORBIDDEN_CLAIMS,
            *product.validation_warnings,
            *[issue.message for issue in safety_result.issues if issue.severity in {"warning", "error"}],
        ]
        visual_identity = _visual_identity(config)

        return ProductReferenceSummary(
            project_id=project_id,
            product_name=product.name,
            brand=product.brand or None,
            industry_preset_id=config.industry.preset_id if config.industry else None,
            visual_identity=visual_identity,
            product_accuracy_lock=_accuracy_lock(product, config, reference_assets),
            allowed_claims=_allowed_claims(product),
            forbidden_claims=forbidden_claims,
            reference_assets=reference_assets,
            main_product_asset_id=main_asset_id,
            warnings=[*warnings, *[issue.message for issue in safety_result.issues if issue.severity == "warning"]],
        )

    def _reference_assets(self, project_id: str, config: ProjectConfig) -> list[ProductReferenceAsset]:
        target_ids = {
            config.assets.main_product_asset_id,
            *config.assets.reference_asset_ids,
            *config.assets.poster_asset_ids,
        }
        target_ids.discard(None)
        assets = self.asset_repository.list_for_project(project_id)
        filtered = [
            asset
            for asset in assets
            if asset.status != ProductAssetStatus.skipped
            and asset.role
            in {
                ProductAssetRole.main_product,
                ProductAssetRole.reference,
                ProductAssetRole.poster,
                ProductAssetRole.thumbnail,
            }
            and (asset.is_selected or asset.id in target_ids or asset.role == ProductAssetRole.main_product)
        ]
        return [_asset_to_reference(asset) for asset in filtered]

    def _warnings(
        self,
        config: ProjectConfig,
        reference_assets: list[ProductReferenceAsset],
        main_asset_id: str | None,
    ) -> list[str]:
        warnings: list[str] = []
        if not reference_assets:
            warnings.append(
                "Chưa có ảnh tham chiếu sản phẩm. Prompt sẽ dựa trên thông tin text, độ chính xác hình ảnh có thể thấp hơn."
            )
        if reference_assets and not main_asset_id:
            warnings.append("Chưa chọn ảnh sản phẩm chính. Prompt Pack sẽ dùng ảnh reference đầu tiên làm tham chiếu phụ.")
        if not config.product.features:
            warnings.append("Product info chưa có danh sách tính năng rõ ràng.")
        return warnings


def _load_project_config(project_id: str) -> ProjectConfig:
    database.init_db()
    project = database.get_project(project_id)
    if not project:
        raise LookupError(f"Project not found: {project_id}")
    try:
        return ProjectConfig.model_validate(project["config"])
    except ValidationError as exc:
        fields = ", ".join(".".join(str(part) for part in error.get("loc", [])) for error in exc.errors())
        raise ValueError(f"Project config không hợp lệ cho Prompt Pack: {fields or exc}") from exc


def _asset_to_reference(asset: ProductAsset) -> ProductReferenceAsset:
    return ProductReferenceAsset(
        asset_id=asset.id,
        role=asset.role.value,
        local_path=asset.local_path,
        original_url=asset.original_url,
        width=asset.width,
        height=asset.height,
        quality_score=asset.quality_score,
        user_note=asset.user_note,
    )


def _main_asset_id(config: ProjectConfig, assets: list[ProductReferenceAsset]) -> str | None:
    if config.assets.main_product_asset_id and any(asset.asset_id == config.assets.main_product_asset_id for asset in assets):
        return config.assets.main_product_asset_id
    main = next((asset for asset in assets if asset.role == ProductAssetRole.main_product.value), None)
    return main.asset_id if main else None


def _visual_identity(config: ProjectConfig) -> str:
    industry = get_industry_preset(config.industry.preset_id if config.industry else None)
    visual_style = get_visual_style_preset(config.visual_style.preset_id)
    template = get_timeline_template(config.timeline.template_id)
    parts = [
        f"Ngành hàng: {industry.name}",
        f"Timeline: {template.name}",
        f"Visual style: {visual_style.name}",
        f"Overlay mode: {config.visual_style.overlay_mode}",
        f"Aspect ratio: {config.render.aspect_ratio}",
    ]
    return "; ".join(parts)


def _accuracy_lock(
    product: ProductInfo,
    config: ProjectConfig,
    assets: list[ProductReferenceAsset],
) -> list[str]:
    locks = [
        f"Giữ đúng sản phẩm: {product.name}",
        f"Giữ đúng thương hiệu: {product.brand}" if product.brand else "Không tự thêm thương hiệu nếu không có trong ảnh hoặc product info.",
        "Dùng ảnh tham chiếu đã chọn làm nguồn sự thật chính cho màu sắc, form dáng, logo và chi tiết sản phẩm.",
        "Không thêm chi tiết vật lý, phụ kiện, logo hoặc chữ trên sản phẩm nếu không có trong dữ liệu.",
    ]
    if assets:
        locks.append(f"Ưu tiên ảnh main_product nếu có; tổng ảnh tham chiếu đang dùng: {len(assets)}.")
    for feature in product.features[:5]:
        locks.append(f"Chỉ thể hiện tính năng đã cung cấp: {feature}")
    for spec in product.specs[:6]:
        locks.append(f"Giữ đúng thông số đã cung cấp: {spec.name}: {spec.value}")

    industry_id = config.industry.preset_id if config.industry else None
    if industry_id == "tech_electronics":
        locks.extend(
            [
                "Không thêm ống kính phụ, anten, cổng kết nối hoặc màn hình UI không có trong ảnh.",
                "Giữ sản phẩm ở bố cục sạch, hiện đại, tránh làm sai model thiết bị.",
            ]
        )
    elif industry_id == "fashion_accessories":
        locks.extend(
            [
                "Giữ đúng form dáng, màu sắc, chất liệu và vị trí logo nếu ảnh tham chiếu thể hiện rõ.",
                "Không đổi sản phẩm thành kiểu áo, túi, giày hoặc phụ kiện khác.",
            ]
        )
    elif industry_id == "beauty_cosmetics":
        locks.extend(
            [
                "Giữ đúng bao bì, nhãn, nắp, màu chai/hộp nếu ảnh tham chiếu thể hiện rõ.",
                "Không thêm claim điều trị hoặc hiệu quả y tế trên bao bì.",
            ]
        )
    elif industry_id == "home_lifestyle":
        locks.append("Giữ đúng kích thước tương đối và cách dùng thực tế trong không gian nhà.")

    return locks


def _allowed_claims(product: ProductInfo) -> list[str]:
    claims: list[str] = []
    claims.extend(product.features)
    claims.extend(f"{spec.name}: {spec.value}" for spec in product.specs)
    return claims
