from __future__ import annotations

from app.modules.content_safety.caption_safety_checker import CaptionSafetyChecker, normalize_hashtags_for_safety
from app.schemas.project_schema import ProductInfo


def test_caption_empty_returns_error() -> None:
    result = CaptionSafetyChecker().check_caption("", ["#review"], _product())

    assert result.passed is False
    assert any(issue.category == "caption_empty" for issue in result.issues)


def test_hashtag_without_hash_is_normalized_with_warning() -> None:
    normalized = normalize_hashtags_for_safety(["review công nghệ", "sanpham"])
    result = CaptionSafetyChecker().check_caption("Caption ổn", ["review công nghệ", "sanpham"], _product())

    assert normalized == ["#reviewcôngnghệ", "#sanpham"]
    assert any(issue.category == "hashtag_format" for issue in result.issues)


def _product() -> ProductInfo:
    return ProductInfo(
        name="Máy chiếu KAW",
        brand="KAW",
        description="Máy chiếu nhỏ gọn hỗ trợ 4K.",
        features=["Hỗ trợ 4K"],
        cta="Xem ngay",
    )
