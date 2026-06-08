from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.api import create_app


def test_product_import_api_accepts_shopee_extension_payload(tmp_path: Path) -> None:
    database.DB_PATH = tmp_path / "product-import-shopee-api.db"

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/product-info/import",
            json={
                "input_type": "shopee_extension",
                "source_name": "shopee",
                "source_url": "https://shopee.vn/May-chieu-KAW-XMAX10-i.123.456",
                "raw_text": "Ten san pham: May chieu KAW XMAX10",
                "structured_data": {
                    "name": "May chieu KAW XMAX10",
                    "brand": "KAW",
                    "description": "May chieu mini ho tro 4K, Android 9.0 va do sang cao.",
                    "features": ["Ho tro 4K", "Android 9.0", "Do sang cao"],
                    "specs": [{"name": "Do sang", "value": "10000 Lumens"}],
                    "cta": "Xem chi tiet san pham tren Shopee",
                    "price": "1.990.000d",
                    "shop": {"name": "KAW Official"},
                },
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["product"]["name"] == "May chieu KAW XMAX10"
    assert payload["product"]["brand"] == "KAW"
    assert payload["source"] == {
        "name": "shopee",
        "url": "https://shopee.vn/May-chieu-KAW-XMAX10-i.123.456",
    }


def test_chrome_extension_origin_is_allowed_by_cors(tmp_path: Path) -> None:
    database.DB_PATH = tmp_path / "product-import-cors.db"

    with TestClient(create_app()) as client:
        response = client.options(
            "/api/health",
            headers={
                "Origin": "chrome-extension://abcdefghijklmnop",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "chrome-extension://abcdefghijklmnop"
