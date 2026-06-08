from __future__ import annotations

import mimetypes
import shutil
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import BinaryIO

from app.modules.product_assets.product_asset_schema import ProductAsset, ProductAssetStatus, ProductAssetType
from app.modules.product_assets.product_asset_validator import ALLOWED_IMAGE_MIME_TYPES, ProductAssetValidator
from app.utils.file_utils import ensure_dir


MAX_IMAGE_BYTES = 15 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 20
MAX_REDIRECTS = 3


class ProductAssetDownloader:
    def __init__(
        self,
        *,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        max_bytes: int = MAX_IMAGE_BYTES,
        validator: ProductAssetValidator | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes
        self.validator = validator or ProductAssetValidator()

    def download_image(self, url: str, output_dir: str, filename_prefix: str) -> ProductAsset:
        now = _now()
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return _failed_asset(url, f"Only http/https image URLs are supported: {url}", now)

        ensure_dir(output_dir)
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "AutoToolProductAssets/1.0",
                "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*;q=0.5",
            },
        )
        opener = urllib.request.build_opener(_LimitedRedirectHandler())
        try:
            with opener.open(request, timeout=self.timeout_seconds) as response:
                content_type = _clean_content_type(response.headers.get("Content-Type"))
                if content_type not in ALLOWED_IMAGE_MIME_TYPES:
                    return _failed_asset(url, f"Unsupported image mime type: {content_type or 'unknown'}", now)

                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > self.max_bytes:
                    return _failed_asset(url, f"Image is larger than {self.max_bytes} bytes.", now)

                extension = _extension_for_mime(content_type)
                target = Path(output_dir) / f"{_safe_prefix(filename_prefix)}{extension}"
                bytes_written = _copy_limited(response, target, self.max_bytes)
        except _TooManyRedirectsError as exc:
            return _failed_asset(url, str(exc), now)
        except _FileTooLargeError as exc:
            return _failed_asset(url, str(exc), now)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return _failed_asset(url, f"Could not download image: {exc}", now)

        validation = self.validator.validate_image(str(target))
        return validation.model_copy(
            update={
                "id": f"download:{url}",
                "original_url": url,
                "asset_type": ProductAssetType.image,
                "status": ProductAssetStatus.downloaded if not validation.errors else ProductAssetStatus.failed,
                "filename": target.name,
                "local_path": str(target),
                "file_size": bytes_written,
                "created_at": now,
                "updated_at": _now(),
            }
        )


class _LimitedRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self) -> None:
        self.redirect_count = 0
        super().__init__()

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        self.redirect_count += 1
        if self.redirect_count > MAX_REDIRECTS:
            raise _TooManyRedirectsError(f"Image URL redirected more than {MAX_REDIRECTS} times.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _FileTooLargeError(Exception):
    pass


class _TooManyRedirectsError(Exception):
    pass


def _copy_limited(response: BinaryIO, target: Path, max_bytes: int) -> int:
    total = 0
    with target.open("wb") as file:
        while True:
            chunk = response.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                file.close()
                try:
                    target.unlink()
                except OSError:
                    pass
                raise _FileTooLargeError(f"Image is larger than {max_bytes} bytes.")
            file.write(chunk)
    return total


def copy_local_image(source_path: str, output_dir: str, filename_prefix: str) -> ProductAsset:
    now = _now()
    source = Path(source_path)
    if not source.exists() or not source.is_file():
        return _failed_asset(source_path, f"Local image does not exist: {source}", now)
    ensure_dir(output_dir)
    mime_type = mimetypes.guess_type(source.name)[0]
    extension = _extension_for_mime(mime_type) if mime_type in ALLOWED_IMAGE_MIME_TYPES else source.suffix.lower()
    target = Path(output_dir) / f"{_safe_prefix(filename_prefix)}{extension or '.jpg'}"
    try:
        shutil.copy2(source, target)
    except OSError as exc:
        return _failed_asset(source_path, f"Could not copy local image: {exc}", now)
    validation = ProductAssetValidator().validate_image(str(target))
    return validation.model_copy(
        update={
            "id": f"copy:{source}",
            "original_url": source_path,
            "asset_type": ProductAssetType.image,
            "status": ProductAssetStatus.downloaded if not validation.errors else ProductAssetStatus.failed,
            "filename": target.name,
            "local_path": str(target),
            "created_at": now,
            "updated_at": _now(),
        }
    )


def _failed_asset(url: str, error: str, now: str) -> ProductAsset:
    return ProductAsset(
        id=f"failed:{url}",
        original_url=url,
        asset_type=ProductAssetType.image,
        status=ProductAssetStatus.failed,
        errors=[error],
        created_at=now,
        updated_at=now,
    )


def _clean_content_type(value: str | None) -> str | None:
    if not value:
        return None
    return value.split(";", 1)[0].strip().lower()


def _extension_for_mime(mime_type: str | None) -> str:
    if mime_type == "image/png":
        return ".png"
    if mime_type == "image/webp":
        return ".webp"
    return ".jpg"


def _safe_prefix(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value.strip())
    return cleaned or "product_asset"


def _now() -> str:
    from datetime import datetime

    return datetime.now().replace(microsecond=0).isoformat()
