from __future__ import annotations

from pathlib import Path

from app import database
from app.modules.product_drafts import CreateProductDraftRequest, ProductDraftService, ProductDraftStatus
from app.modules.product_drafts.product_draft_schema import UpdateProductDraftRequest


def test_product_draft_service_creates_and_updates_draft(tmp_path: Path) -> None:
    database.DB_PATH = tmp_path / "product-draft-service.db"
    database.init_db()
    service = ProductDraftService()

    draft = service.create_from_import_request(
        CreateProductDraftRequest(
            input_type="shopee_extension",
            source_name="shopee",
            source_url="https://shopee.vn/test-i.1.2",
            raw_text="Fallback",
            structured_data={
                "name": "May chieu KAW XMAX10",
                "description": "May chieu mini ho tro 4K va Android 9.0.",
                "features": ["Ho tro 4K", "Android 9.0", "Do sang cao"],
                "specs": [{"name": "Do sang", "value": "10000 Lumens"}],
                "cta": "Xem ngay",
                "shopee": {"warnings": ["Khong tim thay thuong hieu."]},
            },
        )
    )

    assert draft.title == "May chieu KAW XMAX10"
    assert draft.status == ProductDraftStatus.new
    assert any("thuong hieu" in issue.message.casefold() for issue in draft.validation_issues) or draft.normalized_product

    updated = service.update_draft(
        draft.id,
        UpdateProductDraftRequest(status=ProductDraftStatus.reviewed, user_note="Da kiem tra"),
    )

    assert updated.status == ProductDraftStatus.reviewed
    assert updated.user_note == "Da kiem tra"


def test_product_draft_title_fallback_when_name_missing(tmp_path: Path) -> None:
    database.DB_PATH = tmp_path / "product-draft-fallback.db"
    database.init_db()

    draft = ProductDraftService().create_from_import_request(
        CreateProductDraftRequest(
            input_type="shopee_extension",
            source_name="shopee",
            raw_text="",
            structured_data={"description": "", "features": [], "specs": [], "cta": "Xem ngay"},
        )
    )

    assert draft.title == "Untitled product draft"
    assert draft.status == ProductDraftStatus.new
    assert any(issue.severity == "error" for issue in draft.validation_issues)
