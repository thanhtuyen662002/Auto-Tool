from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.api import create_app


def test_product_asset_api_list_import_update_and_file_endpoint(tmp_path: Path, monkeypatch) -> None:
    database.DB_PATH = tmp_path / "product-assets-api.db"

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
        created = client.post("/api/product-info/import", json={**_draft_payload(), "save_to_inbox": True})
        draft_id = created.json()["draft"]["id"]

        listed = client.get(f"/api/product-drafts/{draft_id}/assets")
        first = listed.json()["items"][0]
        imported = client.post(
            f"/api/product-drafts/{draft_id}/assets/import",
            json={"selected_asset_urls": [first["original_url"]], "download_selected": True},
        )
        asset = next(item for item in imported.json()["items"] if item["id"] == first["id"])
        updated = client.put(f"/api/product-assets/{first['id']}", json={"role": "main_product", "is_selected": True})
        file_response = client.get(f"/api/product-assets/{first['id']}/file")
        missing_file = client.get("/api/product-assets/not-a-real-id/file")

    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 2
    assert imported.status_code == 200
    assert asset["status"] == "downloaded"
    assert updated.status_code == 200
    assert updated.json()["items"][0]["role"] == "main_product"
    assert file_response.status_code == 200
    assert missing_file.status_code == 404


def _draft_payload() -> dict:
    return {
        "input_type": "shopee_extension",
        "source_name": "shopee",
        "source_url": "https://shopee.vn/test-i.1.2",
        "raw_text": "Ten san pham: May chieu KAW XMAX10",
        "structured_data": {
            "name": "May chieu KAW XMAX10",
            "brand": "KAW",
            "description": "May chieu mini ho tro 4K va Android 9.0.",
            "features": ["Ho tro 4K", "Android 9.0"],
            "specs": [],
            "cta": "Xem ngay",
            "images": ["https://example.com/a.jpg", "https://example.com/a.jpg"],
            "shopee": {"images": ["https://example.com/b.webp"]},
        },
    }
