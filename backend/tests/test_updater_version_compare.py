from __future__ import annotations

import io
import zipfile

import requests

from app.utils.updater import _download_file, is_newer


def test_release_version_is_newer_than_prerelease() -> None:
    assert is_newer("1.0.0", "1.0.0-rc1") is True


def test_prerelease_numbers_are_ordered() -> None:
    assert is_newer("1.0.0-rc2", "1.0.0-rc1") is True
    assert is_newer("1.0.0-rc1", "1.0.0-rc2") is False


def test_patch_version_is_newer_than_previous_core() -> None:
    assert is_newer("1.0.1", "1.0.0-rc1") is True


def test_prerelease_is_not_newer_than_release_with_same_core() -> None:
    assert is_newer("1.0.1-rc1", "1.0.1") is False


def test_update_download_retries_and_resumes_after_connection_reset(tmp_path, monkeypatch) -> None:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        archive.writestr("AutoTool/AutoTool.exe", "placeholder")
    zip_bytes = zip_buffer.getvalue()
    split_at = 20
    calls: list[dict[str, str]] = []

    class FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str], chunks: list[bytes | Exception]) -> None:
            self.status_code = status_code
            self.headers = headers
            self._chunks = chunks

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise requests.HTTPError(f"HTTP {self.status_code}")

        def iter_content(self, chunk_size: int):
            del chunk_size
            for chunk in self._chunks:
                if isinstance(chunk, Exception):
                    raise chunk
                yield chunk

    def fake_get(url, headers, stream, timeout, allow_redirects):  # noqa: ANN001
        del url, stream, timeout, allow_redirects
        calls.append(dict(headers))
        if len(calls) == 1:
            return FakeResponse(
                200,
                {"Content-Length": str(len(zip_bytes))},
                [zip_bytes[:split_at], requests.ConnectionError("[WinError 10054] connection reset")],
            )
        return FakeResponse(
            206,
            {
                "Content-Length": str(len(zip_bytes) - split_at),
                "Content-Range": f"bytes {split_at}-{len(zip_bytes) - 1}/{len(zip_bytes)}",
            },
            [zip_bytes[split_at:]],
        )

    monkeypatch.setattr("app.utils.updater.requests.get", fake_get)
    monkeypatch.setattr("app.utils.updater.time.sleep", lambda *_args, **_kwargs: None)

    dest = tmp_path / "AutoTool-v1.0.4-windows.zip"
    _download_file("https://example.test/AutoTool.zip", dest, max_attempts=2)

    assert dest.read_bytes() == zip_bytes
    assert not dest.with_suffix(dest.suffix + ".part").exists()
    assert "Range" not in calls[0]
    assert calls[1]["Range"] == f"bytes={split_at}-"
