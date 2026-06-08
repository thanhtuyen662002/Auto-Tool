from __future__ import annotations

import mimetypes
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.modules.product_assets.product_asset_schema import ProductAsset, ProductAssetStatus, ProductAssetType


ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MIN_IMAGE_SIZE = 300


class ProductAssetValidator:
    def validate_image(self, local_path: str) -> ProductAsset:
        path = Path(local_path)
        warnings: list[str] = []
        errors: list[str] = []
        mime_type = mimetypes.guess_type(path.name)[0]
        file_size = path.stat().st_size if path.exists() else 0
        width: int | None = None
        height: int | None = None
        quality_score: float | None = None

        if not path.exists():
            errors.append(f"File does not exist: {path}")
        elif file_size <= 0:
            errors.append("Image file size is 0.")

        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                width, height = image.size
                mime_type = Image.MIME.get(image.format or "", mime_type)
        except (UnidentifiedImageError, OSError) as exc:
            errors.append(f"Could not read image metadata: {exc}")

        if mime_type not in ALLOWED_IMAGE_MIME_TYPES:
            errors.append(f"Unsupported image mime type: {mime_type or 'unknown'}")

        if width is not None and height is not None:
            if width < MIN_IMAGE_SIZE or height < MIN_IMAGE_SIZE:
                warnings.append("Image is smaller than 300px on one side.")
            ratio = max(width / max(height, 1), height / max(width, 1))
            if ratio > 3.5:
                warnings.append("Image aspect ratio is unusually wide or tall.")
            quality_score = _quality_score(width, height, ratio, not errors)

        status = ProductAssetStatus.downloaded if not errors else ProductAssetStatus.failed
        now = _now()
        return ProductAsset(
            id=f"validation:{path}",
            asset_type=ProductAssetType.image,
            status=status,
            filename=path.name,
            local_path=str(path),
            width=width,
            height=height,
            file_size=file_size,
            mime_type=mime_type,
            quality_score=quality_score,
            warnings=warnings,
            errors=errors,
            created_at=now,
            updated_at=now,
        )


def _quality_score(width: int, height: int, ratio: float, metadata_ok: bool) -> float:
    score = 0.0
    if width >= 800:
        score += 0.4
    if height >= 800:
        score += 0.3
    if ratio <= 3.5:
        score += 0.2
    if metadata_ok:
        score += 0.1
    return round(min(score, 1.0), 3)


def _now() -> str:
    from datetime import datetime

    return datetime.now().replace(microsecond=0).isoformat()
