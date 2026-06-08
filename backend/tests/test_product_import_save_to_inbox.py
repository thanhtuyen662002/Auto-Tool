from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.api import create_app


def test_import_with_save_to_inbox_creates_product_draft(tmp_path: Path) -> None:
    database.DB_PATH = tmp_path / "product-import-inbox.db"

    with TestClient(create_app()) as client:
        response = client.post("/api/product-info/import", json={**_shopee_payload(), "save_to_inbox": True})
        drafts = client.get("/api/product-drafts")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["draft"]["title"] == "May chieu KAW XMAX10"
    assert payload["draft"]["status"] == "new"
    assert drafts.status_code == 200
    assert drafts.json()["total"] == 1
    assert drafts.json()["items"][0]["source"]["source_name"] == "shopee"


def test_import_with_save_to_inbox_false_does_not_create_draft(tmp_path: Path) -> None:
    database.DB_PATH = tmp_path / "product-import-no-inbox.db"

    with TestClient(create_app()) as client:
        response = client.post("/api/product-info/import", json={**_shopee_payload(), "save_to_inbox": False})
        drafts = client.get("/api/product-drafts")

    assert response.status_code == 200
    assert response.json().get("draft") is None
    assert drafts.status_code == 200
    assert drafts.json()["total"] == 0


def _shopee_payload() -> dict:
    return {
        "input_type": "shopee_extension",
        "source_name": "shopee",
        "source_url": "https://shopee.vn/May-chieu-KAW-XMAX10-i.123.456",
        "raw_text": "Ten san pham: May chieu KAW XMAX10",
        "structured_data": {
            "name": "May chieu KAW XMAX10",
            "brand": "KAW",
            "description": "May chieu mini ho tro 4K va Android 9.0.",
            "features": ["Ho tro 4K", "Android 9.0", "Do sang cao"],
            "specs": [{"name": "Do sang", "value": "10000 Lumens"}],
            "cta": "Xem chi tiet san pham tren Shopee",
            "price": "1.990.000d",
        },
    }
