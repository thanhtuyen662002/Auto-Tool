from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.api import create_app


def test_product_draft_saves_extractor_debug(tmp_path: Path) -> None:
    database.DB_PATH = tmp_path / "product-draft-extractor-debug.db"

    with TestClient(create_app()) as client:
        import_response = client.post("/api/product-info/import", json=_payload())
        draft_id = import_response.json()["draft"]["id"]
        detail_response = client.get(f"/api/product-drafts/{draft_id}")

    assert import_response.status_code == 200
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["extractor_debug"]["overallConfidence"] == 0.88
    assert detail["extractor_debug"]["fields"][0]["field"] == "name"
    assert detail["extractor_debug"]["fields"][1]["field"] == "brand"
    assert detail["extractor_debug"]["fields"][1]["warnings"] == ["Brand came from DOM specs."]


def _payload() -> dict:
    return {
        "input_type": "shopee_extension",
        "source_name": "shopee",
        "source_url": "https://shopee.vn/May-chieu-KAW-XMAX10-i.123.456",
        "save_to_inbox": True,
        "raw_text": "Ten san pham: May chieu KAW XMAX10",
        "structured_data": {
            "name": "May chieu KAW XMAX10",
            "brand": "KAW",
            "description": "May chieu mini ho tro 4K, Android 11 va do sang cao.",
            "features": ["Ho tro 4K", "Android 11", "Do sang cao"],
            "specs": [{"name": "Do sang", "value": "10000 Lumens"}],
            "cta": "Xem chi tiet san pham tren Shopee",
        },
        "extractor_debug": {
            "url": "https://shopee.vn/May-chieu-KAW-XMAX10-i.123.456",
            "extractedAt": "2026-06-08T00:00:00.000Z",
            "pageType": "product",
            "overallConfidence": 0.88,
            "warnings": ["Khong tim thay JSON-LD Product, mot so field duoc lay bang DOM/text fallback."],
            "fields": [
                {
                    "field": "name",
                    "valueFound": True,
                    "valuePreview": "May chieu KAW XMAX10",
                    "method": "json_ld",
                    "confidence": 0.98,
                    "warnings": [],
                },
                {
                    "field": "brand",
                    "valueFound": True,
                    "valuePreview": "KAW",
                    "method": "dom_selector",
                    "confidence": 0.72,
                    "warnings": ["Brand came from DOM specs."],
                },
            ],
        },
    }
