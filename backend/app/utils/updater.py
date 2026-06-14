from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

import requests

from app.utils.app_paths import executable_dir
from app.version import APP_VERSION

logger = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────────────────

DEFAULT_REPO = "thanhtuyen662002/Auto-Tool"
GITHUB_API_BASE = "https://api.github.com"
DOWNLOAD_CHUNK_SIZE = 1024 * 1024
DOWNLOAD_CONNECT_TIMEOUT_SECONDS = 20
DOWNLOAD_READ_TIMEOUT_SECONDS = 60
DOWNLOAD_RETRY_DELAY_SECONDS = 2
CHECK_INTERVAL_SECONDS = 6 * 3600  # 6 giờ, tránh spam GitHub API

# ─── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class UpdateInfo:
    has_update: bool
    current_version: str
    latest_version: str
    download_url: str | None = None
    html_url: str | None = None
    release_name: str | None = None
    release_notes: str | None = None
    error: str | None = None


@dataclass
class DownloadResult:
    success: bool
    zip_path: str | None = None
    extract_dir: str | None = None
    updater_script: str | None = None
    error: str | None = None


# ─── Version helpers ──────────────────────────────────────────────────────────


def _normalize_version(version: str) -> str:
    """Bỏ prefix 'v' nếu có, ví dụ: 'v1.2.0' -> '1.2.0'."""
    return version.strip().lstrip("v")


def is_newer(remote_version: str, local_version: str) -> bool:
    """True nếu remote_version mới hơn local_version."""
    remote_core, remote_pre = _parse_semver_for_compare(remote_version)
    local_core, local_pre = _parse_semver_for_compare(local_version)
    if remote_core != local_core:
        return remote_core > local_core
    if remote_pre is None and local_pre is not None:
        return True
    if remote_pre is not None and local_pre is None:
        return False
    if remote_pre is None and local_pre is None:
        return False
    return _compare_prerelease(remote_pre or (), local_pre or ()) > 0


def _parse_semver_for_compare(
    version: str,
) -> tuple[tuple[int, int, int], tuple[tuple[int, int | str], ...] | None]:
    clean = _normalize_version(version)
    core_text, _, prerelease_text = clean.split("+", 1)[0].partition("-")
    parts = core_text.split(".")
    try:
        core_parts = [int(part) for part in parts[:3]]
    except ValueError:
        core_parts = [0, 0, 0]
    while len(core_parts) < 3:
        core_parts.append(0)
    return (core_parts[0], core_parts[1], core_parts[2]), _parse_prerelease(prerelease_text)


def _parse_prerelease(value: str) -> tuple[tuple[int, int | str], ...] | None:
    cleaned = value.strip().lower()
    if not cleaned:
        return None
    parts: list[tuple[int, int | str]] = []
    for token in re.findall(r"[a-z]+|\d+", cleaned.replace("_", ".").replace("-", ".")):
        if token.isdigit():
            parts.append((0, int(token)))
        else:
            parts.append((1, token))
    return tuple(parts) or None


def _compare_prerelease(
    remote: tuple[tuple[int, int | str], ...],
    local: tuple[tuple[int, int | str], ...],
) -> int:
    for remote_part, local_part in zip(remote, local):
        if remote_part == local_part:
            continue
        return 1 if remote_part > local_part else -1
    if len(remote) == len(local):
        return 0
    return 1 if len(remote) > len(local) else -1


# ─── GitHub API ──────────────────────────────────────────────────────────────


def _update_enabled() -> bool:
    return os.getenv("AUTO_TOOL_UPDATE_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}


def _github_repo() -> str:
    return os.getenv("AUTO_TOOL_UPDATE_REPO", DEFAULT_REPO).strip()


def _github_token() -> str | None:
    return os.getenv("AUTO_TOOL_GITHUB_TOKEN", "").strip() or None


def _github_api_request(path: str, timeout: int = 10) -> dict:
    url = f"{GITHUB_API_BASE}{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": f"AutoTool/{APP_VERSION}",
    }
    token = _github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


# ─── Check for update ─────────────────────────────────────────────────────────


def check_for_update(current_version: str | None = None) -> UpdateInfo:
    """
    Kiểm tra GitHub Releases API xem có phiên bản mới không.
    Trả về UpdateInfo.has_update=True nếu remote tag mới hơn current_version.
    """
    cur = _normalize_version(current_version or APP_VERSION)
    if not _update_enabled():
        return UpdateInfo(has_update=False, current_version=cur, latest_version=cur)

    repo = _github_repo()
    try:
        data = _github_api_request(f"/repos/{repo}/releases/latest", timeout=10)
    except Exception as exc:
        logger.debug("Update check failed: %s", exc)
        return UpdateInfo(
            has_update=False,
            current_version=cur,
            latest_version=cur,
            error=str(exc),
        )

    tag = data.get("tag_name", "")
    latest = _normalize_version(tag)
    html_url = data.get("html_url", "")
    release_name = data.get("name", tag)
    release_notes = (data.get("body") or "").strip()[:2000]  # Giới hạn độ dài

    # Tìm asset ZIP trong release
    download_url: str | None = None
    for asset in data.get("assets", []):
        name: str = asset.get("name", "")
        if name.endswith(".zip") and "windows" in name.lower():
            download_url = asset.get("browser_download_url")
            break
    # Fallback: dùng zipball của release
    if not download_url:
        download_url = data.get("zipball_url")

    has_update = is_newer(latest, cur)
    return UpdateInfo(
        has_update=has_update,
        current_version=cur,
        latest_version=latest,
        download_url=download_url if has_update else None,
        html_url=html_url,
        release_name=release_name,
        release_notes=release_notes,
    )


# ─── Download & prepare update (Option B) ────────────────────────────────────


def download_and_prepare_update(info: UpdateInfo) -> DownloadResult:
    """
    Tải ZIP của phiên bản mới về thư mục `_update/` cạnh EXE,
    giải nén ra và tạo script `_update.bat` để người dùng chạy sau khi đóng app.
    """
    if not info.download_url:
        return DownloadResult(success=False, error="Không có link download.")

    exe_dir = executable_dir()
    update_dir = exe_dir / "_update"
    update_dir.mkdir(parents=True, exist_ok=True)

    zip_name = f"AutoTool-v{info.latest_version}-windows.zip"
    zip_path = update_dir / zip_name
    extract_dir = update_dir / f"AutoTool-v{info.latest_version}"

    # Tải ZIP
    try:
        _download_file(info.download_url, zip_path)
    except Exception as exc:
        return DownloadResult(success=False, error=f"Tải về thất bại: {exc}")

    # Giải nén
    try:
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)
        zip_path.unlink(missing_ok=True)
    except Exception as exc:
        return DownloadResult(success=False, error=f"Giải nén thất bại: {exc}")

    # Xác định thư mục con chứa AutoTool.exe
    inner = _find_autotool_dir(extract_dir)
    copy_from = str(inner) if inner else str(extract_dir)

    # Tạo _update.bat cạnh EXE
    bat_path = exe_dir / "_update.bat"
    bat_content = _build_updater_bat(
        exe_name="AutoTool.exe",
        copy_from=copy_from,
        exe_dir=str(exe_dir),
        update_dir=str(update_dir),
    )
    bat_path.write_text(bat_content, encoding="utf-8")

    # Khởi chạy script cập nhật trong tiến trình độc lập (chỉ Windows)
    if sys.platform == "win32":
        try:
            flags = 0
            if hasattr(subprocess, "CREATE_NEW_CONSOLE"):
                flags |= subprocess.CREATE_NEW_CONSOLE
            if hasattr(subprocess, "DETACHED_PROCESS"):
                flags |= subprocess.DETACHED_PROCESS
            
            subprocess.Popen(
                [str(bat_path)],
                creationflags=flags,
                shell=True,
                cwd=str(exe_dir)
            )
            logger.info("Updater script launched successfully.")
        except Exception as exc:
            logger.error("Failed to launch updater script: %s", exc)
            return DownloadResult(success=False, error=f"Không thể khởi chạy script cập nhật: {exc}")
    else:
        logger.warning("Not on Windows, updater script was not launched automatically.")

    logger.info("Update prepared at %s. Updater script: %s", extract_dir, bat_path)
    return DownloadResult(
        success=True,
        zip_path=None,
        extract_dir=str(extract_dir),
        updater_script=str(bat_path),
    )


def _download_file(url: str, dest: Path, timeout: int = 180, max_attempts: int | None = None) -> None:
    """Download a release asset with retry and resume support."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        if zipfile.is_zipfile(dest):
            logger.info("Using existing update archive: %s", dest)
            return
        dest.unlink(missing_ok=True)

    tmp = dest.with_suffix(dest.suffix + ".part")
    legacy_tmp = dest.with_suffix(dest.suffix + ".download")
    if legacy_tmp.exists() and not tmp.exists():
        legacy_tmp.replace(tmp)

    attempts = max_attempts or _download_retry_count()
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            _download_file_once(url, tmp, timeout=timeout)
            if not zipfile.is_zipfile(tmp):
                raise RuntimeError("File ZIP tải về không hợp lệ hoặc chưa tải đủ dữ liệu.")
            tmp.replace(dest)
            return
        except Exception as exc:
            last_error = exc
            logger.warning("Update download attempt %s/%s failed: %s", attempt, attempts, exc)
            if attempt < attempts:
                time.sleep(min(DOWNLOAD_RETRY_DELAY_SECONDS * attempt, 10))

    raise RuntimeError(_format_download_error(last_error, attempts))


def _download_file_once(url: str, tmp: Path, timeout: int) -> None:
    resume_from = tmp.stat().st_size if tmp.exists() else 0
    headers = _download_headers(resume_from if resume_from > 0 else None)
    request_timeout = (
        DOWNLOAD_CONNECT_TIMEOUT_SECONDS,
        max(DOWNLOAD_READ_TIMEOUT_SECONDS, timeout),
    )

    with requests.get(
        url,
        headers=headers,
        stream=True,
        timeout=request_timeout,
        allow_redirects=True,
    ) as response:
        if resume_from > 0 and response.status_code == 416:
            tmp.unlink(missing_ok=True)
            raise RuntimeError("Máy chủ không chấp nhận phần đã tải trước đó, Auto Tool sẽ tải lại từ đầu.")

        if resume_from > 0 and response.status_code != 206:
            tmp.unlink(missing_ok=True)
            raise RuntimeError("Máy chủ không hỗ trợ tải tiếp, Auto Tool sẽ tải lại từ đầu.")

        response.raise_for_status()
        expected_size = _expected_download_size(response, resume_from)
        mode = "ab" if resume_from > 0 and response.status_code == 206 else "wb"
        bytes_written = 0
        with tmp.open(mode) as file:
            for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                if not chunk:
                    continue
                file.write(chunk)
                bytes_written += len(chunk)

    final_size = tmp.stat().st_size if tmp.exists() else 0
    if bytes_written <= 0:
        raise RuntimeError("Máy chủ không gửi dữ liệu cập nhật.")
    if expected_size is not None and final_size < expected_size:
        raise RuntimeError(f"Tải chưa đủ dữ liệu ({final_size}/{expected_size} bytes).")


def _download_headers(range_start: int | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": f"AutoTool/{APP_VERSION} (+https://github.com/{DEFAULT_REPO})",
        "Accept": "application/octet-stream, application/zip, */*",
        "Accept-Encoding": "identity",
    }
    token = _github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if range_start is not None and range_start > 0:
        headers["Range"] = f"bytes={range_start}-"
    return headers


def _expected_download_size(response: requests.Response, resume_from: int) -> int | None:
    content_range = response.headers.get("Content-Range", "")
    match = re.search(r"/(\d+)\s*$", content_range)
    if match:
        return int(match.group(1))
    content_length = response.headers.get("Content-Length")
    if not content_length or not content_length.isdigit():
        return None
    length = int(content_length)
    return resume_from + length if response.status_code == 206 else length


def _download_retry_count() -> int:
    value = os.getenv("AUTO_TOOL_UPDATE_DOWNLOAD_RETRIES", "5").strip()
    try:
        return max(1, int(value))
    except ValueError:
        return 5


def _format_download_error(error: Exception | None, attempts: int) -> str:
    detail = str(error or "không rõ nguyên nhân")
    network_reset = "10054" in detail or "forcibly closed" in detail.lower() or isinstance(
        error,
        (requests.ConnectionError, requests.Timeout),
    )
    if network_reset:
        return (
            f"Kết nối tải bản cập nhật bị GitHub/CDN, mạng, VPN/proxy hoặc antivirus đóng giữa chừng. "
            f"Auto Tool đã thử lại {attempts} lần và giữ file .part để lần sau tải tiếp. "
            f"Hãy bấm cập nhật lại, đổi mạng/tắt VPN nếu có, hoặc tải ZIP thủ công từ trang GitHub Release. "
            f"Lỗi cuối: {detail}"
        )
    return f"Không thể tải bản cập nhật sau {attempts} lần. Lỗi cuối: {detail}"


def _find_autotool_dir(root: Path) -> Path | None:
    """Tìm thư mục con chứa AutoTool.exe trong extract dir."""
    if (root / "AutoTool.exe").exists():
        return root
    for child in root.iterdir():
        if child.is_dir() and (child / "AutoTool.exe").exists():
            return child
    return None


def _build_updater_bat(
    exe_name: str,
    copy_from: str,
    exe_dir: str,
    update_dir: str,
) -> str:
    """Tạo nội dung file _update.bat để chạy sau khi đóng app."""
    return f"""\
@echo off
chcp 65001 > nul
echo ===========================================
echo   AutoTool Updater
echo ===========================================
echo.
echo Dang cho AutoTool tat...
:wait_loop
tasklist /FI "IMAGENAME eq {exe_name}" 2>nul | find /I "{exe_name}" > nul
if not errorlevel 1 (
    timeout /t 2 /nobreak > nul
    goto wait_loop
)
echo.
echo Dang cap nhat AutoTool...
xcopy /E /Y /I "{copy_from}\\*" "{exe_dir}\\" > nul
if errorlevel 1 (
    echo.
    echo [LOI] Cap nhat that bai! Vui long thu lai thu cong.
    echo  - Giai nen file ZIP vao thu muc: {exe_dir}
    pause
    exit /b 1
)
echo.
echo Don dep...
rd /S /Q "{update_dir}" 2>nul
echo.
echo Cap nhat hoan tat! Dang khoi dong lai AutoTool...
timeout /t 2 /nobreak > nul
start "" "{exe_dir}\\{exe_name}"
(goto) 2>nul & del "%~f0"
"""


# ─── Background check ─────────────────────────────────────────────────────────

_update_cache: UpdateInfo | None = None
_update_cache_time: float = 0.0
_update_lock = threading.Lock()


def get_cached_update_info(force: bool = False) -> UpdateInfo:
    """
    Trả về UpdateInfo từ cache nếu còn hạn (6h), hoặc fetch mới nếu hết hạn.
    Thread-safe.
    """
    global _update_cache, _update_cache_time
    with _update_lock:
        now = time.monotonic()
        if not force and _update_cache is not None and (now - _update_cache_time) < CHECK_INTERVAL_SECONDS:
            return _update_cache
        try:
            info = check_for_update()
        except Exception as exc:
            info = UpdateInfo(
                has_update=False,
                current_version=_normalize_version(APP_VERSION),
                latest_version=_normalize_version(APP_VERSION),
                error=str(exc),
            )
        _update_cache = info
        _update_cache_time = now
        return info
