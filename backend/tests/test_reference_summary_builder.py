from __future__ import annotations

import pytest

from app.modules.product_reference_prompt.reference_summary_builder import ProductReferenceSummaryBuilder
from backend.tests.prompt_pack_helpers import add_main_asset, make_invalid_project_missing_name, make_project


def test_reference_summary_builds_accuracy_lock_from_product_info(tmp_path) -> None:
    project_id = make_project(tmp_path)

    summary = ProductReferenceSummaryBuilder().build_summary(project_id)

    assert summary.product_name == "Máy Chiếu 4K Android KAW XMAX10"
    assert any("Giữ đúng sản phẩm" in item for item in summary.product_accuracy_lock)
    assert "Hỗ trợ 4K" in summary.allowed_claims
    assert "Độ phân giải: 4K" in summary.allowed_claims


def test_reference_summary_without_asset_returns_warning(tmp_path) -> None:
    project_id = make_project(tmp_path)

    summary = ProductReferenceSummaryBuilder().build_summary(project_id)

    assert summary.reference_assets == []
    assert any("Chưa có ảnh tham chiếu" in warning for warning in summary.warnings)


def test_reference_summary_includes_main_product_asset(tmp_path) -> None:
    project_id = make_project(tmp_path)
    add_main_asset(project_id, tmp_path)

    summary = ProductReferenceSummaryBuilder().build_summary(project_id)

    assert summary.main_product_asset_id == "asset-main"
    assert summary.reference_assets[0].asset_id == "asset-main"
    assert summary.reference_assets[0].role == "main_product"


def test_reference_summary_adds_safety_warning_to_forbidden_claims(tmp_path) -> None:
    project_id = make_project(tmp_path, brand="")

    summary = ProductReferenceSummaryBuilder().build_summary(project_id)

    assert any("thương hiệu" in claim.casefold() or "thÆ°Æ¡ng" in claim.casefold() for claim in summary.forbidden_claims)


def test_reference_summary_invalid_product_name_fails_clearly(tmp_path) -> None:
    project_id = make_invalid_project_missing_name(tmp_path)

    with pytest.raises(ValueError, match="product.name|Project config"):
        ProductReferenceSummaryBuilder().build_summary(project_id)
