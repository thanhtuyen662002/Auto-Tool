from __future__ import annotations

from pathlib import Path

from app import database
from app.modules.product_assets.product_asset_repository import ProductAssetRepository
from app.modules.product_assets.product_asset_schema import ProductAsset, ProductAssetRole, ProductAssetStatus, ProductAssetType


def make_project(tmp_path: Path, project_id: str = "project-1", industry_id: str | None = "tech_electronics", brand: str = "KAW") -> str:
    database.DB_PATH = tmp_path / f"{project_id}.db"
    database.init_db()
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)
    config = {
        "project_name": "prompt-pack-test",
        "source_folder": str(source_dir),
        "output_folder": str(output_dir),
        "product": {
            "name": "Máy Chiếu 4K Android KAW XMAX10",
            "brand": brand,
            "description": "Máy chiếu giải trí gia đình nhỏ gọn, hỗ trợ 4K, Android 9.0.",
            "features": ["Hỗ trợ 4K", "Android 9.0", "Thiết kế nhỏ gọn"],
            "specs": [{"name": "Độ phân giải", "value": "4K"}],
            "cta": "Xem chi tiết sản phẩm ngay",
        },
        "render": {"output_count": 1, "duration": 8, "aspect_ratio": "9:16", "resolution": "1080x1920", "fps": 30},
        "effects": {"cut_intensity": 70, "speed_variation": 30, "grain": 0, "zoom_motion": 0, "overlay_height": 33, "subtitle_size": 84},
        "ai": {"text_model": "gemini-test", "tone": "friendly_reviewer", "language": "vi", "gemini_api_keys": []},
        "industry": {"preset_id": industry_id} if industry_id else None,
        "assets": {"main_product_asset_id": "asset-main", "reference_asset_ids": ["asset-ref"], "poster_asset_ids": []},
    }
    database.create_project(project_id, config)
    return project_id


def add_main_asset(project_id: str, tmp_path: Path) -> ProductAsset:
    image_path = tmp_path / "main-product.jpg"
    image_path.write_bytes(b"fake-image")
    asset = ProductAsset(
        id="asset-main",
        project_id=project_id,
        original_url="https://example.com/main.jpg",
        asset_type=ProductAssetType.image,
        role=ProductAssetRole.main_product,
        status=ProductAssetStatus.downloaded,
        filename=image_path.name,
        local_path=str(image_path),
        width=1200,
        height=1200,
        file_size=10,
        mime_type="image/jpeg",
        quality_score=0.95,
        is_selected=True,
        created_at="2026-06-09T00:00:00",
        updated_at="2026-06-09T00:00:00",
    )
    return ProductAssetRepository().upsert(asset)


def make_invalid_project_missing_name(tmp_path: Path) -> str:
    project_id = "invalid-project"
    database.DB_PATH = tmp_path / "invalid-project.db"
    database.init_db()
    config = {
        "project_name": "invalid",
        "source_folder": str(tmp_path),
        "output_folder": str(tmp_path / "outputs"),
        "product": {
            "name": "",
            "brand": "Brand",
            "description": "Description",
            "features": ["Feature"],
            "cta": "CTA",
        },
        "render": {"output_count": 1, "duration": 8, "aspect_ratio": "9:16", "resolution": "1080x1920", "fps": 30},
        "effects": {"cut_intensity": 70, "speed_variation": 30, "grain": 0, "zoom_motion": 0, "overlay_height": 33, "subtitle_size": 84},
        "ai": {"text_model": "gemini-test", "tone": "friendly_reviewer", "language": "vi", "gemini_api_keys": []},
    }
    database.create_project(project_id, config)
    return project_id
