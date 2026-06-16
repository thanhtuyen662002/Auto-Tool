from __future__ import annotations

import io
import subprocess
import zipfile

import requests

from app.utils.updater import _download_file, _launch_updater_script, check_for_update, is_newer


def test_release_version_is_newer_than_prerelease() -> None:
    assert is_newer("1.0.0", "1.0.0-rc1") is True


def test_prerelease_numbers_are_ordered() -> None:
    assert is_newer("1.0.0-rc2", "1.0.0-rc1") is True
    assert is_newer("1.0.0-rc1", "1.0.0-rc2") is False


def test_patch_version_is_newer_than_previous_core() -> None:
    assert is_newer("1.0.1", "1.0.0-rc1") is True


def test_prerelease_is_not_newer_than_release_with_same_core() -> None:
    assert is_newer("1.0.1-rc1", "1.0.1") is False


def test_check_for_update_selects_windows_release_asset(monkeypatch) -> None:
    def fake_request(path, timeout):  # noqa: ANN001
        assert path.endswith("/releases/latest")
        assert timeout == 10
        return {
            "tag_name": "v1.0.12",
            "html_url": "https://github.com/example/repo/releases/tag/v1.0.12",
            "name": "v1.0.12",
            "body": "notes",
            "assets": [
                {"name": "source.zip", "browser_download_url": "https://example.test/source.zip"},
                {"name": "AutoTool-v1.0.12-windows.zip", "browser_download_url": "https://example.test/windows.zip"},
            ],
        }

    monkeypatch.setattr("app.utils.updater._github_api_request", fake_request)

    info = check_for_update("1.0.11")

    assert info.has_update is True
    assert info.latest_version == "1.0.12"
    assert info.download_url == "https://example.test/windows.zip"


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


def test_launch_updater_script_uses_valid_windows_process_flags(tmp_path, monkeypatch) -> None:
    calls: list[dict] = []
    bat_path = tmp_path / "_update.bat"
    exe_dir = tmp_path / "AutoTool"
    exe_dir.mkdir()
    bat_path.write_text("@echo off\n", encoding="utf-8")

    monkeypatch.setattr("app.utils.updater.subprocess.CREATE_NEW_CONSOLE", 0x00000010, raising=False)
    monkeypatch.setattr("app.utils.updater.subprocess.DETACHED_PROCESS", 0x00000008, raising=False)

    def fake_popen(args, **kwargs):  # noqa: ANN001
        calls.append({"args": args, **kwargs})

        class FakeProcess:
            pass

        return FakeProcess()

    monkeypatch.setattr("app.utils.updater.subprocess.Popen", fake_popen)

    _launch_updater_script(bat_path=bat_path, exe_dir=exe_dir)

    assert calls
    call = calls[0]
    assert call["args"] == ["cmd.exe", "/d", "/c", str(bat_path)]
    assert call["cwd"] == str(exe_dir)
    assert call["shell"] is False
    assert call["creationflags"] == subprocess.CREATE_NEW_CONSOLE
    assert call["creationflags"] & subprocess.DETACHED_PROCESS == 0
