from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

from app.modules.product_assets.product_asset_downloader import ProductAssetDownloader
from app.modules.product_assets.product_asset_schema import ProductAssetStatus


def test_downloader_downloads_valid_image_with_mocked_http(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.modules.product_assets.product_asset_downloader.urllib.request.build_opener",
        lambda *_args, **_kwargs: FakeOpener(FakeResponse(_png_bytes(), "image/png")),
    )

    asset = ProductAssetDownloader().download_image("https://example.com/image.png", str(tmp_path), "product_asset_001")

    assert asset.status == ProductAssetStatus.downloaded
    assert asset.width == 800
    assert asset.height == 800
    assert asset.mime_type == "image/png"
    assert Path(asset.local_path or "").exists()


def test_downloader_rejects_non_image_mime_type(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.modules.product_assets.product_asset_downloader.urllib.request.build_opener",
        lambda *_args, **_kwargs: FakeOpener(FakeResponse(b"not image", "text/html")),
    )

    asset = ProductAssetDownloader().download_image("https://example.com/file.html", str(tmp_path), "product_asset_001")

    assert asset.status == ProductAssetStatus.failed
    assert "Unsupported image mime type" in asset.errors[0]


def test_downloader_rejects_file_larger_than_limit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.modules.product_assets.product_asset_downloader.urllib.request.build_opener",
        lambda *_args, **_kwargs: FakeOpener(FakeResponse(b"123456", "image/jpeg")),
    )

    asset = ProductAssetDownloader(max_bytes=3).download_image("https://example.com/large.jpg", str(tmp_path), "product_asset_001")

    assert asset.status == ProductAssetStatus.failed
    assert "larger" in asset.errors[0]


class FakeOpener:
    def __init__(self, response: "FakeResponse") -> None:
        self.response = response

    def open(self, _request, timeout: int):  # noqa: ANN001
        return self.response


class FakeResponse:
    def __init__(self, body: bytes, mime_type: str) -> None:
        self._buffer = BytesIO(body)
        self.headers = {
            "Content-Type": mime_type,
            "Content-Length": str(len(body)),
        }

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args) -> None:  # noqa: ANN002
        self._buffer.close()

    def read(self, size: int = -1) -> bytes:
        return self._buffer.read(size)


def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (800, 800), color=(255, 255, 255)).save(output, format="PNG")
    return output.getvalue()
