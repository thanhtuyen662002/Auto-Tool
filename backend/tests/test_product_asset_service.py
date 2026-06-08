from __future__ import annotations

from pathlib import Path

from app import database
from app.modules.product_assets import ProductAssetService, ProductAssetStatus
from app.modules.product_drafts import CreateProductDraftRequest, ProductDraftService


def test_draft_images_create_pending_assets_and_deduplicate(tmp_path: Path) -> None:
    database.DB_PATH = tmp_path / "assets-service.db"
    database.init_db()
    draft = ProductDraftService().create_from_import_request(_draft_request())

    assets = ProductAssetService().list_assets_for_draft(draft.id)

    assert len(assets) == 2
    assert assets[0].status == ProductAssetStatus.pending
    assert assets[0].role == "main_product"
    assert assets[1].role == "reference"


def test_attach_selected_assets_to_project_updates_project_config(tmp_path: Path, monkeypatch) -> None:
    database.DB_PATH = tmp_path / "assets-attach.db"
    database.init_db()
    draft = ProductDraftService().create_from_import_request(_draft_request())
    project = database.create_project("project-1", _project_config(tmp_path))
    assets = ProductAssetService().list_assets_for_draft(draft.id)

    def fake_download_image(url: str, output_dir: str, filename_prefix: str):
        from app.modules.product_assets.product_asset_schema import ProductAsset, ProductAssetStatus, ProductAssetType

        path = Path(output_dir) / f"{filename_prefix}.jpg"
        path.write_bytes(b"fake")
        return ProductAsset(
            id="downloaded",
            original_url=url,
            asset_type=ProductAssetType.image,
            status=ProductAssetStatus.downloaded,
            filename=path.name,
            local_path=str(path),
            width=1200,
            height=1200,
            file_size=4,
            mime_type="image/jpeg",
            quality_score=1.0,
            created_at="2026-06-08T00:00:00",
            updated_at="2026-06-08T00:00:00",
        )

    service = ProductAssetService()
    monkeypatch.setattr(service.downloader, "download_image", fake_download_image)

    attached = service.attach_draft_assets_to_project(draft.id, project["project_id"], [assets[0].id])
    updated_project = database.get_project(project["project_id"])

    assert len(attached) == 1
    assert attached[0].project_id == project["project_id"]
    assert updated_project is not None
    assert updated_project["config"]["assets"]["main_product_asset_id"] == assets[0].id


def _draft_request() -> CreateProductDraftRequest:
    return CreateProductDraftRequest(
        input_type="shopee_extension",
        source_name="shopee",
        source_url="https://shopee.vn/test-i.1.2",
        raw_text="Ten san pham: Test",
        structured_data={
            "name": "May chieu KAW XMAX10",
            "description": "May chieu mini ho tro 4K va Android 9.0.",
            "features": ["Ho tro 4K", "Android 9.0"],
            "specs": [],
            "cta": "Xem ngay",
            "images": ["https://example.com/a.jpg", "https://example.com/a.jpg"],
            "shopee": {"images": ["https://example.com/b.webp"]},
        },
    )


def _project_config(tmp_path: Path) -> dict:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir()
    output_dir.mkdir()
    return {
        "project_name": "asset-project",
        "source_folder": str(source_dir),
        "output_folder": str(output_dir),
        "product": {
            "name": "Test product",
            "brand": "Test",
            "description": "Description",
            "features": ["Feature"],
            "specs": [],
            "cta": "Xem ngay",
        },
        "render": {"output_count": 1, "duration": 8, "aspect_ratio": "9:16", "resolution": "1080x1920", "fps": 30},
        "effects": {"cut_intensity": 70, "speed_variation": 30, "grain": 0, "zoom_motion": 0, "overlay_height": 33, "subtitle_size": 84},
        "ai": {"text_model": "gemini-test", "tone": "friendly_reviewer", "language": "vi", "gemini_api_keys": []},
    }
