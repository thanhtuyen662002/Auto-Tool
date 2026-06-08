from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.api import create_app


def test_product_draft_api_list_update_archive_delete_and_clear(tmp_path: Path) -> None:
    database.DB_PATH = tmp_path / "product-draft-api.db"

    with TestClient(create_app()) as client:
        created = client.post("/api/product-info/import", json={**_payload("Draft One"), "save_to_inbox": True}).json()
        draft_id = created["draft"]["id"]

        listed = client.get("/api/product-drafts", params={"status": "new"})
        detail = client.get(f"/api/product-drafts/{draft_id}")
        updated = client.put(f"/api/product-drafts/{draft_id}", json={"status": "reviewed", "user_note": "OK"})
        archived = client.post(f"/api/product-drafts/{draft_id}/archive")
        clear_empty = client.post("/api/product-drafts/clear-archived")

        second = client.post("/api/product-info/import", json={**_payload("Draft Two"), "save_to_inbox": True}).json()
        second_id = second["draft"]["id"]
        deleted = client.delete(f"/api/product-drafts/{second_id}")

    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert detail.status_code == 200
    assert detail.json()["title"] == "Draft One"
    assert updated.status_code == 200
    assert updated.json()["status"] == "reviewed"
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert clear_empty.status_code == 200
    assert clear_empty.json()["deleted_count"] == 1
    assert deleted.status_code == 200
    assert deleted.json()["success"] is True


def _payload(name: str) -> dict:
    return {
        "input_type": "shopee_extension",
        "source_name": "shopee",
        "source_url": f"https://shopee.vn/{name.replace(' ', '-')}-i.1.2",
        "raw_text": f"Ten san pham: {name}",
        "structured_data": {
            "name": name,
            "brand": "KAW",
            "description": "May chieu mini ho tro 4K va Android 9.0.",
            "features": ["Ho tro 4K", "Android 9.0", "Do sang cao"],
            "specs": [{"name": "Do sang", "value": "10000 Lumens"}],
            "cta": "Xem ngay",
        },
    }
