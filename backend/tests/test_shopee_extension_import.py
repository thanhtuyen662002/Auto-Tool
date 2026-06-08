from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.api import create_app


def test_shopee_extension_import_creates_draft_and_returns_inbox_url(tmp_path: Path) -> None:
    database.DB_PATH = tmp_path / "shopee-extension-import.db"

    with TestClient(create_app()) as client:
        response = client.post("/api/product-info/import", json=_payload())
        drafts = client.get("/api/product-drafts")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["draft"]["title"] == "May chieu KAW XMAX10"
    assert body["import_inbox_url"] == "http://localhost:5173/import-inbox"
    assert drafts.status_code == 200
    assert drafts.json()["total"] == 1


def test_shopee_extension_import_missing_name_returns_clear_issue(tmp_path: Path) -> None:
    database.DB_PATH = tmp_path / "shopee-extension-import-missing-name.db"
    payload = _payload()
    payload["structured_data"]["name"] = ""
    payload["raw_text"] = "URL: https://shopee.vn/May-chieu-KAW-XMAX10-i.123.456"

    with TestClient(create_app()) as client:
        response = client.post("/api/product-info/import", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["draft"]["status"] == "new"
    assert any(issue["field"] == "name" and issue["severity"] == "error" for issue in body["issues"])
    assert "traceback" not in response.text.lower()


def _payload() -> dict:
    return {
        "input_type": "shopee_extension",
        "source_name": "shopee",
        "source_url": "https://shopee.vn/May-chieu-KAW-XMAX10-i.123.456",
        "save_to_inbox": True,
        "raw_text": "Ten san pham: May chieu KAW XMAX10\nURL: https://shopee.vn/May-chieu-KAW-XMAX10-i.123.456",
        "structured_data": {
            "name": "May chieu KAW XMAX10",
            "brand": "KAW",
            "description": "May chieu mini ho tro 4K, Android 11 va do sang cao.",
            "features": ["Ho tro 4K", "Android 11", "Do sang cao"],
            "specs": [{"name": "Do sang", "value": "10000 Lumens"}],
            "cta": "Xem chi tiet san pham tren Shopee",
            "price": "1.990.000d",
        },
        "extractor_debug": {
            "url": "https://shopee.vn/May-chieu-KAW-XMAX10-i.123.456",
            "extractedAt": "2026-06-08T00:00:00.000Z",
            "pageType": "product",
            "overallConfidence": 0.88,
            "warnings": [],
            "fields": [
                {
                    "field": "name",
                    "valueFound": True,
                    "valuePreview": "May chieu KAW XMAX10",
                    "method": "json_ld",
                    "confidence": 0.98,
                    "warnings": [],
                }
            ],
        },
    }
