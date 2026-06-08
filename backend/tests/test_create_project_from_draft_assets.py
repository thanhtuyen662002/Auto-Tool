from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.api import create_app


def test_create_project_from_draft_with_assets_updates_config(tmp_path: Path, monkeypatch) -> None:
    database.DB_PATH = tmp_path / "create-project-assets.db"
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir()
    output_dir.mkdir()

    def fake_download_image(self, url: str, output_dir: str, filename_prefix: str):  # noqa: ANN001
        from app.modules.product_assets.product_asset_schema import ProductAsset, ProductAssetStatus, ProductAssetType

        path = Path(output_dir) / f"{filename_prefix}.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"image")
        return ProductAsset(
            id="downloaded",
            original_url=url,
            asset_type=ProductAssetType.image,
            status=ProductAssetStatus.downloaded,
            filename=path.name,
            local_path=str(path),
            width=1200,
            height=1200,
            file_size=5,
            mime_type="image/jpeg",
            quality_score=1.0,
            created_at="2026-06-08T00:00:00",
            updated_at="2026-06-08T00:00:00",
        )

    monkeypatch.setattr(
        "app.modules.product_assets.product_asset_downloader.ProductAssetDownloader.download_image",
        fake_download_image,
    )

    with TestClient(create_app()) as client:
        created_draft = client.post("/api/product-info/import", json={**_draft_payload(), "save_to_inbox": True})
        draft_id = created_draft.json()["draft"]["id"]
        listed = client.get(f"/api/product-drafts/{draft_id}/assets")
        asset_id = listed.json()["items"][0]["id"]

        created_project = client.post(
            f"/api/product-drafts/{draft_id}/create-project",
            json={
                "project_name": "kaw-xmax10",
                "source_folder": str(source_dir),
                "output_folder": str(output_dir),
                "render": {"output_count": 3, "duration": 12},
                "attach_selected_assets": True,
                "selected_asset_ids": [asset_id],
            },
        )
        project_id = created_project.json()["project_id"]
        project = client.get(f"/api/projects/{project_id}")
        project_assets = client.get(f"/api/projects/{project_id}/assets")

    assert created_project.status_code == 200
    assert project.status_code == 200
    assert project.json()["config"]["assets"]["main_product_asset_id"] == asset_id
    assert project_assets.status_code == 200
    assert project_assets.json()["items"][0]["status"] == "downloaded"


def _draft_payload() -> dict:
    return {
        "input_type": "shopee_extension",
        "source_name": "shopee",
        "source_url": "https://shopee.vn/May-chieu-KAW-XMAX10-i.1.2",
        "raw_text": "Ten san pham: May chieu KAW XMAX10",
        "structured_data": {
            "name": "May chieu KAW XMAX10",
            "brand": "KAW",
            "description": "May chieu mini ho tro 4K va Android 9.0.",
            "features": ["Ho tro 4K", "Android 9.0", "Do sang cao"],
            "specs": [{"name": "Do sang", "value": "10000 Lumens"}],
            "cta": "Xem ngay",
            "images": ["https://example.com/main.jpg"],
        },
    }
