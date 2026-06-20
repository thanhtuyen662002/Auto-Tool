from __future__ import annotations

import os
import platform
import random
import re
import shutil
import subprocess
import threading
import time
import uuid
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.modules.douyin_downloader.downloader_schema import (
    DouyinDownloaderHistoryResponse,
    DouyinDownloaderChannelDownloadHistory,
    DouyinDownloaderJobActionResponse,
    DouyinDownloaderJobResponse,
    DouyinDownloaderOutputItem,
    DouyinDownloaderStatusResponse,
)
from app.utils.app_paths import app_data_dir


DOUYIN_HOME_URL = "https://www.douyin.com/"
DEFAULT_SCAN_UNTIL_END_SCROLL_LIMIT = 5000
SCAN_NO_NEW_LINK_LIMIT = 18
DOWNLOAD_HISTORY_LIMIT = 20000
SCANNED_CHANNEL_HISTORY_LIMIT = 60
SCANNED_LINKS_PER_CHANNEL_LIMIT = 10000
LOGIN_COOKIE_NAMES = {
    "sessionid",
    "sessionid_ss",
    "sid_guard",
    "uid_tt",
    "uid_tt_ss",
    "passport_csrf_token",
}


class DouyinDownloaderError(RuntimeError):
    pass


class _DownloadPaused(RuntimeError):
    pass


@dataclass
class _DownloadJob:
    job_id: str
    job_type: str
    status: str = "queued"
    current_step: str = "Đang chờ xử lý"
    progress: int = 0
    total_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    output_folder: str | None = None
    skip_existing: bool = True
    pause_requested: bool = False
    links: list[str] = field(default_factory=list)
    outputs: list[dict[str, Any]] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().replace(microsecond=0).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().replace(microsecond=0).isoformat())

    def touch(self) -> None:
        self.updated_at = datetime.now().replace(microsecond=0).isoformat()

    def log(self, message: str) -> None:
        cleaned = self._short_message(message)
        if not cleaned:
            return
        if self.logs and self.logs[-1] == cleaned:
            self.touch()
            return
        self.logs.append(cleaned)
        self.logs = self.logs[-80:]
        self.touch()

    def fail_item(self, message: str) -> None:
        self.failed_items += 1
        self.errors.append(self._short_message(message, limit=260))
        self.errors = self.errors[-30:]
        self.log(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "status": self.status,
            "current_step": self.current_step,
            "progress": self.progress,
            "total_items": self.total_items,
            "completed_items": self.completed_items,
            "failed_items": self.failed_items,
            "output_folder": self.output_folder,
            "skip_existing": self.skip_existing,
            "pause_requested": self.pause_requested,
            "links": list(self.links),
            "outputs": list(self.outputs),
            "logs": list(self.logs),
            "errors": list(self.errors),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "_DownloadJob":
        job = cls(
            job_id=str(payload.get("job_id") or uuid.uuid4()),
            job_type=str(payload.get("job_type") or "download"),
            status=str(payload.get("status") or "queued"),
            current_step=str(payload.get("current_step") or "Đang chờ xử lý"),
            progress=int(payload.get("progress") or 0),
            total_items=int(payload.get("total_items") or 0),
            completed_items=int(payload.get("completed_items") or 0),
            failed_items=int(payload.get("failed_items") or 0),
            output_folder=payload.get("output_folder"),
            skip_existing=bool(payload.get("skip_existing", True)),
            pause_requested=bool(payload.get("pause_requested", False)),
            links=[str(item) for item in payload.get("links") or []],
            outputs=[dict(item) for item in payload.get("outputs") or [] if isinstance(item, dict)],
            logs=[str(item) for item in payload.get("logs") or []],
            errors=[str(item) for item in payload.get("errors") or []],
            created_at=str(payload.get("created_at") or datetime.now().replace(microsecond=0).isoformat()),
            updated_at=str(payload.get("updated_at") or datetime.now().replace(microsecond=0).isoformat()),
        )
        if job.status in {"queued", "running"}:
            job.status = "paused"
            job.pause_requested = False
            job.current_step = "Tác vụ bị gián đoạn, có thể tiếp tục tải."
            job.log("Tác vụ bị gián đoạn do ứng dụng đã đóng. Bạn có thể bấm Tiếp tục tải.")
        return job

    def _short_message(self, message: str, limit: int = 220) -> str:
        cleaned = re.sub(r"\s+", " ", str(message or "")).strip()
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 1].rstrip() + "…"

    def to_response(self) -> DouyinDownloaderJobResponse:
        return DouyinDownloaderJobResponse(
            job_id=self.job_id,
            job_type=self.job_type,  # type: ignore[arg-type]
            status=self.status,  # type: ignore[arg-type]
            current_step=self.current_step,
            progress=max(0, min(100, int(self.progress))),
            total_items=self.total_items,
            completed_items=self.completed_items,
            failed_items=self.failed_items,
            output_folder=self.output_folder,
            skip_existing=self.skip_existing,
            pause_requested=self.pause_requested,
            links=list(self.links),
            outputs=[DouyinDownloaderOutputItem.model_validate(item) for item in self.outputs],
            logs=list(self.logs[-80:]),
            errors=list(self.errors[-30:]),
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class DouyinDownloaderService:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or app_data_dir()
        self.runtime_dir = self.data_dir / "douyin_downloader"
        self.profile_dir = self.runtime_dir / "chrome_profile"
        self.driver_cache_dir = self.runtime_dir / "drivers"
        self.cookie_dir = self.runtime_dir / "cookies"
        self.jobs_dir = self.runtime_dir / "jobs"
        self.history_path = self.runtime_dir / "history.json"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.driver_cache_dir.mkdir(parents=True, exist_ok=True)
        self.cookie_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

        self._driver: Any | None = None
        self._chrome_path: str | None = None
        self._driver_path: str | None = None
        self._browser_lock = threading.RLock()
        self._jobs: dict[str, _DownloadJob] = {}
        self._jobs_lock = threading.RLock()
        self._history_lock = threading.RLock()
        self._history = self._load_history()
        self._load_persisted_jobs()

    def get_status(self) -> DouyinDownloaderStatusResponse:
        with self._browser_lock:
            driver = self._driver
            chrome_path = self._chrome_path or self.find_chrome_path()
            if not driver:
                return DouyinDownloaderStatusResponse(
                    browser_open=False,
                    logged_in=False,
                    chrome_path=chrome_path,
                    driver_path=self._driver_path,
                    profile_dir=str(self.profile_dir),
                    message="Trình duyệt Douyin chưa mở.",
                )
            try:
                current_url = driver.current_url
                page_title = driver.title
                logged_in = self._has_login_cookie(driver.get_cookies())
                message = "Đã phát hiện phiên đăng nhập Douyin." if logged_in else "Chưa phát hiện phiên đăng nhập Douyin."
            except Exception:
                self._driver = None
                return DouyinDownloaderStatusResponse(
                    browser_open=False,
                    logged_in=False,
                    chrome_path=chrome_path,
                    driver_path=self._driver_path,
                    profile_dir=str(self.profile_dir),
                    message="Trình duyệt đã đóng hoặc mất kết nối.",
                )
            return DouyinDownloaderStatusResponse(
                browser_open=True,
                logged_in=logged_in,
                chrome_path=chrome_path,
                driver_path=self._driver_path,
                profile_dir=str(self.profile_dir),
                current_url=current_url,
                page_title=page_title,
                message=message,
            )

    def open_browser(self, start_url: str | None = None) -> DouyinDownloaderStatusResponse:
        with self._browser_lock:
            if self._driver:
                try:
                    self._driver.get(start_url or DOUYIN_HOME_URL)
                    return self.get_status()
                except Exception:
                    self._driver = None

            webdriver, Service = self._import_selenium()
            chrome_path = self.find_chrome_path()
            if not chrome_path:
                raise DouyinDownloaderError(
                    "Không tìm thấy Google Chrome trên máy. Hãy cài Google Chrome rồi mở lại tính năng tải Douyin."
                )

            options = webdriver.ChromeOptions()
            options.binary_location = chrome_path
            options.add_argument(f"--user-data-dir={self.profile_dir}")
            options.add_argument("--profile-directory=Default")
            options.add_argument("--start-maximized")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            driver_path = self.get_chromedriver_path()
            service = Service(driver_path) if driver_path else Service()
            if os.name == "nt":
                service.creation_flags = subprocess.CREATE_NO_WINDOW

            try:
                driver = webdriver.Chrome(service=service, options=options)
            except Exception as first_exc:
                if not driver_path:
                    raise DouyinDownloaderError(
                        "Không thể mở ChromeDriver. Nếu Chrome vừa cập nhật, hãy đóng Chrome rồi thử lại. "
                        f"Chi tiết: {first_exc}"
                    ) from first_exc
                try:
                    fallback_service = Service()
                    if os.name == "nt":
                        fallback_service.creation_flags = subprocess.CREATE_NO_WINDOW
                    driver = webdriver.Chrome(service=fallback_service, options=options)
                    driver_path = None
                except Exception as second_exc:
                    raise DouyinDownloaderError(
                        "Không thể mở ChromeDriver. Nếu Chrome vừa cập nhật, hãy đóng Chrome rồi thử lại. "
                        f"ChromeDriver đã tải lỗi: {first_exc}. Selenium Manager cũng lỗi: {second_exc}"
                    ) from second_exc

            self._driver = driver
            self._chrome_path = chrome_path
            self._driver_path = driver_path
            driver.get(start_url or DOUYIN_HOME_URL)
            return self.get_status()

    def close_browser(self) -> str:
        with self._browser_lock:
            if not self._driver:
                return "Trình duyệt Douyin chưa mở."
            try:
                self._driver.quit()
            finally:
                self._driver = None
            return "Đã đóng trình duyệt Douyin."

    def check_login(self) -> DouyinDownloaderStatusResponse:
        return self.get_status()

    def start_scan(self, channel_url: str, max_scrolls: int = DEFAULT_SCAN_UNTIL_END_SCROLL_LIMIT, scan_until_end: bool = True) -> DouyinDownloaderJobResponse:
        self._require_browser()
        job = self._create_job("scan")
        self._remember_channel_url(channel_url)
        thread = threading.Thread(target=self._run_scan_job, args=(job.job_id, channel_url, max_scrolls, scan_until_end), daemon=True)
        thread.start()
        return job.to_response()

    def start_download(self, links: list[str], output_folder: str, skip_existing: bool = True, channel_url: str | None = None) -> DouyinDownloaderJobResponse:
        self._require_browser()
        cleaned_links = self._clean_links(links)
        if not cleaned_links:
            raise DouyinDownloaderError("Chưa có đường dẫn Douyin nào để tải.")
        output_dir = Path(output_folder).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        job = self._create_job("download")
        job.links = cleaned_links
        job.total_items = len(cleaned_links)
        job.output_folder = str(output_dir)
        job.skip_existing = skip_existing
        job.touch()
        self._remember_output_folder(str(output_dir))
        if channel_url:
            self._remember_channel_download(channel_url, str(output_dir), cleaned_links)
        self._save_job(job)
        thread = threading.Thread(target=self._run_download_job, args=(job.job_id, cleaned_links, output_dir, skip_existing), daemon=True)
        thread.start()
        return job.to_response()

    def get_job(self, job_id: str) -> DouyinDownloaderJobResponse | None:
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            return job.to_response() if job else None

    def get_history(self) -> DouyinDownloaderHistoryResponse:
        with self._jobs_lock:
            recent_jobs = sorted(self._jobs.values(), key=lambda item: item.updated_at, reverse=True)[:20]
        with self._history_lock:
            downloaded = {
                link: DouyinDownloaderOutputItem.model_validate(item)
                for link, item in (self._history.get("downloaded_links") or {}).items()
                if isinstance(item, dict)
            }
            return DouyinDownloaderHistoryResponse(
                recent_channel_urls=list(self._history.get("recent_channel_urls") or [])[:20],
                recent_output_folders=list(self._history.get("recent_output_folders") or [])[:20],
                recent_jobs=[job.to_response() for job in recent_jobs],
                downloaded_links=downloaded,
                scanned_channels={
                    str(channel): [str(link) for link in links]
                    for channel, links in (self._history.get("scanned_channels") or {}).items()
                    if isinstance(links, list)
                },
                channel_downloads={
                    str(channel): DouyinDownloaderChannelDownloadHistory.model_validate(item)
                    for channel, item in (self._history.get("channel_downloads") or {}).items()
                    if isinstance(item, dict)
                },
            )

    def pause_job(self, job_id: str) -> DouyinDownloaderJobActionResponse:
        job = self._must_get_job(job_id)
        if job.job_type not in {"scan", "download"}:
            raise DouyinDownloaderError("Chỉ hỗ trợ dừng tạm thời tác vụ tải video.")
        if job.status not in {"queued", "running"}:
            return DouyinDownloaderJobActionResponse(success=True, message="Tác vụ không còn đang tải.", job=job.to_response())
        job.pause_requested = True
        job.current_step = "Đang dừng sau video hiện tại"
        job.log("Đã yêu cầu dừng tải. Ứng dụng sẽ dừng an toàn sau video hiện tại.")
        self._save_job(job)
        return DouyinDownloaderJobActionResponse(success=True, message="Đã gửi yêu cầu dừng tải.", job=job.to_response())

    def resume_job(self, job_id: str) -> DouyinDownloaderJobActionResponse:
        self._require_browser()
        job = self._must_get_job(job_id)
        if job.job_type != "download":
            raise DouyinDownloaderError("Chỉ hỗ trợ tiếp tục tác vụ tải video.")
        if job.status in {"queued", "running"}:
            return DouyinDownloaderJobActionResponse(success=True, message="Tác vụ đang chạy.", job=job.to_response())
        if not job.output_folder:
            raise DouyinDownloaderError("Tác vụ cũ không có thư mục lưu nên không thể tiếp tục.")
        remaining_links = self._remaining_download_links(job)
        if not remaining_links:
            job.status = "completed"
            job.pause_requested = False
            job.progress = 100
            job.current_step = "Không còn video nào cần tải"
            job.log("Tất cả video đã tải hoặc đã được bỏ qua.")
            self._save_job(job)
            return DouyinDownloaderJobActionResponse(success=True, message="Không còn video nào cần tải.", job=job.to_response())
        job.status = "queued"
        job.pause_requested = False
        job.current_step = "Đang chuẩn bị tiếp tục tải"
        job.log(f"Tiếp tục tải {len(remaining_links)} video còn lại.")
        self._save_job(job)
        thread = threading.Thread(
            target=self._run_download_job,
            args=(job.job_id, remaining_links, Path(job.output_folder).expanduser().resolve(), job.skip_existing),
            daemon=True,
        )
        thread.start()
        return DouyinDownloaderJobActionResponse(success=True, message="Đã tiếp tục tải video.", job=job.to_response())

    def find_chrome_path(self) -> str | None:
        configured = os.getenv("AUTO_TOOL_CHROME_PATH", "").strip()
        candidates: list[str | None] = [configured or None]
        system = platform.system().lower()
        if system == "windows":
            candidates.extend(
                [
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                    str(Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "Application" / "chrome.exe"),
                    shutil.which("chrome"),
                    shutil.which("google-chrome"),
                ]
            )
        elif system == "darwin":
            candidates.extend(
                [
                    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                    shutil.which("google-chrome"),
                    shutil.which("chrome"),
                ]
            )
        else:
            candidates.extend([shutil.which("google-chrome"), shutil.which("google-chrome-stable"), shutil.which("chromium"), shutil.which("chrome")])

        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return str(Path(candidate).resolve())
        return None

    def get_chromedriver_path(self) -> str | None:
        cached = self._find_cached_chromedriver()
        if cached:
            return cached
        try:
            from webdriver_manager.chrome import ChromeDriverManager  # type: ignore
            from webdriver_manager.core.driver_cache import DriverCacheManager  # type: ignore

            cache_manager = DriverCacheManager(root_dir=str(self.driver_cache_dir))
            driver_path = ChromeDriverManager(cache_manager=cache_manager).install()
            if driver_path and Path(driver_path).exists():
                return str(Path(driver_path).resolve())
        except Exception:
            return None
        return None

    def _run_scan_job(self, job_id: str, channel_url: str, max_scrolls: int, scan_until_end: bool = True) -> None:
        job = self._must_get_job(job_id)
        max_scrolls = max(1, int(max_scrolls or DEFAULT_SCAN_UNTIL_END_SCROLL_LIMIT))
        if scan_until_end:
            max_scrolls = max(max_scrolls, DEFAULT_SCAN_UNTIL_END_SCROLL_LIMIT)
        job.status = "running"
        job.current_step = "Đang mở trang Douyin"
        job.log("Bắt đầu quét đường dẫn video Douyin.")
        job.touch()
        try:
            with self._browser_lock:
                driver = self._require_browser()
                self._import_wait_tools()
                driver.get(channel_url)
                self._wait_for_body(driver, timeout=20)
                time.sleep(2)
                links: set[str] = set()
                last_count = 0
                stuck_count = 0
                for index in range(max_scrolls):
                    if job.pause_requested:
                        self._mark_job_paused(job)
                        return
                    anchors = driver.find_elements("css selector", 'a[href*="/video/"]')
                    for anchor in anchors:
                        href = anchor.get_attribute("href")
                        if href:
                            normalized_href = self._normalize_link(href)
                            if normalized_href and not self._is_note_link(normalized_href):
                                links.add(normalized_href)
                    current_count = len(links)
                    job.links = sorted(links)
                    job.total_items = current_count
                    if scan_until_end:
                        job.progress = min(95, max(job.progress, int(((index + 1) / max_scrolls) * 95)))
                        job.current_step = f"Đang quét tới cuối kênh: đã cuộn {index + 1} lần, tìm được {current_count} video"
                    else:
                        job.progress = int(((index + 1) / max_scrolls) * 95)
                        job.current_step = f"Đang cuộn trang ({index + 1}/{max_scrolls})"
                    if index == 0 or index % 5 == 4:
                        job.log(f"Đã tìm thấy {current_count} đường dẫn video.")

                    if anchors:
                        try:
                            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'end'});", anchors[-1])
                        except Exception:
                            driver.execute_script("window.scrollBy(0, 2400);")
                    else:
                        driver.execute_script("window.scrollBy(0, 2400);")
                    time.sleep(random.uniform(1.0, 1.8))

                    if current_count == last_count:
                        stuck_count += 1
                        if stuck_count >= 4:
                            driver.execute_script("window.scrollBy(0, -900);")
                            time.sleep(0.6)
                            driver.execute_script("window.scrollBy(0, 3000);")
                    else:
                        stuck_count = 0
                    last_count = current_count
                    if stuck_count >= SCAN_NO_NEW_LINK_LIMIT:
                        job.log("Trang không tải thêm video mới, dừng quét.")
                        break

            job.links = sorted(links)
            self._remember_scanned_channel_links(channel_url, job.links)
            job.completed_items = len(job.links)
            job.progress = 100
            job.status = "completed"
            job.current_step = "Quét đường dẫn hoàn tất"
            job.log(f"Hoàn tất quét Douyin: {len(job.links)} đường dẫn.")
        except Exception as exc:
            job.status = "failed"
            job.current_step = "Quét đường dẫn thất bại"
            job.errors.append(str(exc))
            job.log(f"Quét đường dẫn thất bại: {exc}")
        finally:
            job.touch()
            self._save_job(job)

    def _run_download_job(self, job_id: str, links: list[str], output_dir: Path, skip_existing: bool) -> None:
        job = self._must_get_job(job_id)
        job.status = "running"
        job.output_folder = str(output_dir)
        job.skip_existing = skip_existing
        job.current_step = "Đang chuẩn bị tải video"
        job.log(f"Bắt đầu tải {len(links)} video vào thư mục đã chọn.")
        job.touch()
        self._save_job(job)
        try:
            for index, link in enumerate(links, start=1):
                if job.pause_requested:
                    self._mark_job_paused(job)
                    return
                job.current_step = f"Đang tải video {index}/{len(links)}"
                job.progress = self._job_progress_from_outputs(job)
                self._save_job(job)
                try:
                    historical = self._history_output_for_link(link)
                    if skip_existing and historical and self._history_file_exists(historical):
                        result = {
                            "link": link,
                            "title": historical.get("title"),
                            "path": historical.get("path"),
                            "status": "skipped",
                            "message": f"Bỏ qua vì video đã tải trước đó: {Path(str(historical.get('path'))).name}",
                        }
                    else:
                        result = self._download_one(link, output_dir, skip_existing, job)
                    self._upsert_output(job, result)
                    if result["status"] in {"success", "skipped"}:
                        self._remember_downloaded_link(link, result)
                    job.log(result["message"])
                except _DownloadPaused:
                    self._mark_job_paused(job)
                    return
                except Exception as exc:
                    message = f"Tải thất bại: {link} - {exc}"
                    job.fail_item(message)
                    self._upsert_output(
                        job,
                        {
                            "link": link,
                            "title": None,
                            "path": None,
                            "status": "failed",
                            "message": message,
                        },
                    )
                self._refresh_job_counts(job)
                job.progress = self._job_progress_from_outputs(job)
                job.touch()
                self._save_job(job)
                time.sleep(random.uniform(0.8, 1.8))

            self._refresh_job_counts(job)
            job.progress = 100
            job.status = "completed" if job.completed_items > 0 else "failed"
            job.current_step = "Tải video hoàn tất" if job.completed_items > 0 else "Không tải được video nào"
            job.log(f"Hoàn tất tải: thành công {job.completed_items}, lỗi {job.failed_items}.")
        except Exception as exc:
            job.status = "failed"
            job.current_step = "Tải video thất bại"
            job.errors.append(str(exc))
            job.log(f"Tải video thất bại: {exc}")
        finally:
            job.touch()
            self._save_job(job)

    def _download_one(self, link: str, output_dir: Path, skip_existing: bool, job: _DownloadJob | None = None) -> dict[str, Any]:
        if self._is_note_link(link):
            return {
                "link": link,
                "title": None,
                "path": None,
                "status": "skipped",
                "message": "Bỏ qua bài Douyin dạng ảnh/slide, chỉ tải bài có video thật.",
            }
        resolved = self._resolve_video(link)
        title = resolved.get("title") or f"douyin_{int(time.time())}"
        safe_title = self._safe_filename(title)
        existing = sorted(output_dir.glob(f"{safe_title}.*"))
        if skip_existing:
            for file in existing:
                if file.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv"} and self._is_valid_downloaded_video_file(file):
                    return {
                        "link": link,
                        "title": title,
                        "path": str(file),
                        "status": "skipped",
                        "message": f"Bỏ qua vì video đã tồn tại: {file.name}",
                    }

        mp4_url = resolved.get("mp4_url")
        if mp4_url and not str(mp4_url).startswith("blob:"):
            output_path = output_dir / f"{safe_title}.mp4"
            self._download_direct(str(mp4_url), output_path, resolved.get("cookies") or [], job)
            try:
                self._validate_downloaded_video(output_path)
            except Exception:
                output_path.unlink(missing_ok=True)
                if job:
                    job.log("Link tải trực tiếp không tạo được video xem được, chuyển sang phương án tải dự phòng.")
                output_path = self._download_with_ytdlp(link, output_dir, safe_title, resolved.get("cookies") or [])
                self._validate_downloaded_video(output_path)
                return {
                    "link": link,
                    "title": title,
                    "path": str(output_path),
                    "status": "success",
                    "message": f"Đã tải xong bằng phương án dự phòng: {output_path.name}",
                }
            return {
                "link": link,
                "title": title,
                "path": str(output_path),
                "status": "success",
                "message": f"Đã tải xong: {output_path.name}",
            }

        output_path = self._download_with_ytdlp(link, output_dir, safe_title, resolved.get("cookies") or [])
        self._validate_downloaded_video(output_path)
        return {
            "link": link,
            "title": title,
            "path": str(output_path),
            "status": "success",
            "message": f"Đã tải xong: {output_path.name}",
        }

    def _resolve_video(self, link: str) -> dict[str, Any]:
        with self._browser_lock:
            driver = self._require_browser()
            original_handle = driver.current_window_handle
            cookies: list[dict[str, Any]] = []
            try:
                driver.execute_script("window.open(arguments[0], '_blank');", link)
                driver.switch_to.window(driver.window_handles[-1])
                self._wait_for_body(driver, timeout=20)
                time.sleep(2)
                title = self._extract_title(driver)
                mp4_url = self._extract_video_src(driver)
                cookies = driver.get_cookies()
                return {"title": title, "mp4_url": mp4_url, "cookies": cookies}
            finally:
                try:
                    if len(driver.window_handles) > 1:
                        driver.close()
                    driver.switch_to.window(original_handle)
                except Exception:
                    pass

    def _download_direct(self, url: str, output_path: Path, cookies: list[dict[str, Any]], job: _DownloadJob | None = None) -> None:
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        session = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        session.mount("http://", HTTPAdapter(max_retries=retries))
        session.mount("https://", HTTPAdapter(max_retries=retries))
        cookie_dict = {str(cookie.get("name")): str(cookie.get("value")) for cookie in cookies if cookie.get("name")}
        headers = {
            "User-Agent": self._user_agent(),
            "Referer": DOUYIN_HOME_URL,
        }
        response = session.get(url, headers=headers, cookies=cookie_dict, stream=True, timeout=30)
        response.raise_for_status()
        partial_path = output_path.with_suffix(output_path.suffix + ".part")
        try:
            with partial_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if job and job.pause_requested:
                        raise _DownloadPaused("Người dùng đã dừng tải.")
                    if chunk:
                        handle.write(chunk)
            partial_path.replace(output_path)
        except _DownloadPaused:
            partial_path.unlink(missing_ok=True)
            raise
        except Exception:
            partial_path.unlink(missing_ok=True)
            raise
        if not output_path.exists() or output_path.stat().st_size <= 0:
            raise DouyinDownloaderError("File tải về bị rỗng.")

    def _download_with_ytdlp(self, link: str, output_dir: Path, safe_title: str, cookies: list[dict[str, Any]]) -> Path:
        try:
            import yt_dlp  # type: ignore
        except Exception as exc:
            raise DouyinDownloaderError("Chưa cài yt-dlp nên không thể dùng phương án tải dự phòng.") from exc

        cookie_file = self._write_cookie_file(cookies)
        out_template = str(output_dir / f"{safe_title}.%(ext)s")
        before = {path.resolve() for path in output_dir.glob(f"{safe_title}.*")}
        options = {
            "outtmpl": out_template,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "merge_output_format": "mp4",
            "cookiefile": str(cookie_file),
        }
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([link])
        after = sorted(
            [path for path in output_dir.glob(f"{safe_title}.*") if path.resolve() not in before and path.stat().st_size > 0],
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        if after:
            return after[0]
        existing = sorted([path for path in output_dir.glob(f"{safe_title}.*") if path.stat().st_size > 0], key=lambda item: item.stat().st_mtime, reverse=True)
        if existing:
            return existing[0]
        raise DouyinDownloaderError("yt-dlp không tạo được file video.")

    def _extract_title(self, driver: Any) -> str:
        candidates: list[str] = []
        try:
            candidates.append(str(driver.title or ""))
        except Exception:
            pass
        for selector in ["h1", '[data-e2e="video-desc"]', 'meta[property="og:title"]']:
            try:
                elements = driver.find_elements("css selector", selector)
                for element in elements:
                    value = element.get_attribute("content") if selector.startswith("meta") else element.text
                    if value:
                        candidates.append(str(value))
            except Exception:
                continue
        for value in candidates:
            cleaned = re.sub(r"\s+", " ", value).strip(" -_")
            if cleaned:
                return cleaned[:120]
        return f"douyin_{int(time.time())}"

    def _extract_video_src(self, driver: Any) -> str | None:
        for selector in ["video", "video source"]:
            try:
                elements = driver.find_elements("css selector", selector)
                for element in elements:
                    src = element.get_attribute("src")
                    if src and not str(src).startswith("blob:"):
                        return str(src)
            except Exception:
                continue
        return None

    def _write_cookie_file(self, cookies: list[dict[str, Any]]) -> Path:
        cookie_file = self.cookie_dir / "douyin_cookies.txt"
        now = int(time.time())
        lines = ["# Netscape HTTP Cookie File\n"]
        for cookie in cookies:
            name = str(cookie.get("name") or "").strip()
            value = str(cookie.get("value") or "")
            if not name:
                continue
            domain = str(cookie.get("domain") or ".douyin.com")
            include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
            path = str(cookie.get("path") or "/")
            secure = "TRUE" if cookie.get("secure") else "FALSE"
            expires = int(cookie.get("expiry") or (now + 60 * 60 * 24 * 30))
            lines.append("\t".join([domain, include_subdomains, path, secure, str(expires), name, value]) + "\n")
        cookie_file.write_text("".join(lines), encoding="utf-8")
        return cookie_file

    def _load_history(self) -> dict[str, Any]:
        default = {"recent_channel_urls": [], "recent_output_folders": [], "downloaded_links": {}, "scanned_channels": {}, "channel_downloads": {}}
        if not self.history_path.exists():
            return default
        try:
            payload = json.loads(self.history_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return default
            scanned_payload = payload.get("scanned_channels") or {}
            if not isinstance(scanned_payload, dict):
                scanned_payload = {}
            channel_downloads_payload = payload.get("channel_downloads") or {}
            if not isinstance(channel_downloads_payload, dict):
                channel_downloads_payload = {}
            return {
                "recent_channel_urls": list(payload.get("recent_channel_urls") or [])[:20],
                "recent_output_folders": list(payload.get("recent_output_folders") or [])[:20],
                "downloaded_links": dict(payload.get("downloaded_links") or {}),
                "scanned_channels": {
                    str(channel): [str(link) for link in links]
                    for channel, links in scanned_payload.items()
                    if isinstance(links, list)
                },
                "channel_downloads": {
                    str(channel): dict(item)
                    for channel, item in channel_downloads_payload.items()
                    if isinstance(item, dict)
                },
            }
        except Exception:
            return default

    def _save_history(self) -> None:
        with self._history_lock:
            self.history_path.write_text(json.dumps(self._history, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_persisted_jobs(self) -> None:
        loaded: list[_DownloadJob] = []
        for path in self.jobs_dir.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    loaded.append(_DownloadJob.from_dict(payload))
            except Exception:
                continue
        loaded.sort(key=lambda item: item.updated_at)
        with self._jobs_lock:
            self._jobs = {job.job_id: job for job in loaded[-100:]}
        for job in loaded[-100:]:
            self._save_job(job)

    def _save_job(self, job: _DownloadJob) -> None:
        path = self.jobs_dir / f"{job.job_id}.json"
        path.write_text(json.dumps(job.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def _remember_channel_url(self, channel_url: str) -> None:
        normalized = self._normalize_link(channel_url)
        if not normalized:
            return
        with self._history_lock:
            self._history["recent_channel_urls"] = self._prepend_unique(self._history.get("recent_channel_urls") or [], normalized, 20)
            self._save_history()

    def _remember_scanned_channel_links(self, channel_url: str, links: list[str]) -> None:
        normalized = self._normalize_link(channel_url)
        if not normalized:
            return
        clean_links = self._clean_links(links)[:SCANNED_LINKS_PER_CHANNEL_LIMIT]
        with self._history_lock:
            scanned = dict(self._history.get("scanned_channels") or {})
            scanned[normalized] = clean_links
            if len(scanned) > SCANNED_CHANNEL_HISTORY_LIMIT:
                scanned = dict(list(scanned.items())[-SCANNED_CHANNEL_HISTORY_LIMIT:])
            self._history["scanned_channels"] = scanned
            channel_downloads = dict(self._history.get("channel_downloads") or {})
            existing = dict(channel_downloads.get(normalized) or {})
            channel_downloads[normalized] = {
                "channel_url": normalized,
                "output_folder": existing.get("output_folder"),
                "links": clean_links,
                "total_links": len(clean_links),
                "updated_at": datetime.now().replace(microsecond=0).isoformat(),
            }
            if len(channel_downloads) > SCANNED_CHANNEL_HISTORY_LIMIT:
                channel_downloads = dict(list(channel_downloads.items())[-SCANNED_CHANNEL_HISTORY_LIMIT:])
            self._history["channel_downloads"] = channel_downloads
            self._save_history()

    def _remember_output_folder(self, output_folder: str) -> None:
        value = str(Path(output_folder).expanduser().resolve())
        with self._history_lock:
            self._history["recent_output_folders"] = self._prepend_unique(self._history.get("recent_output_folders") or [], value, 20)
            self._save_history()

    def _remember_channel_download(self, channel_url: str, output_folder: str, links: list[str]) -> None:
        normalized = self._normalize_link(channel_url)
        if not normalized:
            return
        clean_links = self._clean_links(links)[:SCANNED_LINKS_PER_CHANNEL_LIMIT]
        with self._history_lock:
            self._history["recent_channel_urls"] = self._prepend_unique(self._history.get("recent_channel_urls") or [], normalized, 20)
            self._history["recent_output_folders"] = self._prepend_unique(self._history.get("recent_output_folders") or [], output_folder, 20)
            scanned = dict(self._history.get("scanned_channels") or {})
            if clean_links:
                scanned[normalized] = clean_links
                if len(scanned) > SCANNED_CHANNEL_HISTORY_LIMIT:
                    scanned = dict(list(scanned.items())[-SCANNED_CHANNEL_HISTORY_LIMIT:])
            self._history["scanned_channels"] = scanned
            channel_downloads = dict(self._history.get("channel_downloads") or {})
            channel_downloads[normalized] = {
                "channel_url": normalized,
                "output_folder": output_folder,
                "links": clean_links or list(scanned.get(normalized) or []),
                "total_links": len(clean_links or list(scanned.get(normalized) or [])),
                "updated_at": datetime.now().replace(microsecond=0).isoformat(),
            }
            if len(channel_downloads) > SCANNED_CHANNEL_HISTORY_LIMIT:
                channel_downloads = dict(list(channel_downloads.items())[-SCANNED_CHANNEL_HISTORY_LIMIT:])
            self._history["channel_downloads"] = channel_downloads
            self._save_history()

    def _remember_downloaded_link(self, link: str, result: dict[str, Any]) -> None:
        normalized = self._normalize_link(link)
        if not normalized:
            return
        with self._history_lock:
            downloaded = dict(self._history.get("downloaded_links") or {})
            downloaded[normalized] = {
                "link": normalized,
                "title": result.get("title"),
                "path": result.get("path"),
                "status": result.get("status"),
                "message": result.get("message") or "",
            }
            if len(downloaded) > DOWNLOAD_HISTORY_LIMIT:
                downloaded = dict(list(downloaded.items())[-DOWNLOAD_HISTORY_LIMIT:])
            self._history["downloaded_links"] = downloaded
            self._save_history()

    def _prepend_unique(self, values: list[Any], item: str, limit: int) -> list[str]:
        result = [item]
        for value in values:
            text = str(value)
            if text and text != item and text not in result:
                result.append(text)
            if len(result) >= limit:
                break
        return result

    def _history_output_for_link(self, link: str) -> dict[str, Any] | None:
        normalized = self._normalize_link(link)
        with self._history_lock:
            item = (self._history.get("downloaded_links") or {}).get(normalized)
            return dict(item) if isinstance(item, dict) else None

    def _history_file_exists(self, item: dict[str, Any]) -> bool:
        path = item.get("path")
        if not path:
            return False
        try:
            file = Path(str(path)).expanduser()
            return self._is_valid_downloaded_video_file(file)
        except Exception:
            return False

    def _is_note_link(self, link: str) -> bool:
        return "/note/" in self._normalize_link(link).lower()

    def _is_valid_downloaded_video_file(self, path: Path) -> bool:
        try:
            self._validate_downloaded_video(path)
            return True
        except Exception:
            return False

    def _validate_downloaded_video(self, path: Path) -> None:
        if not path.exists() or not path.is_file() or path.stat().st_size <= 0:
            raise DouyinDownloaderError("File tải về bị rỗng hoặc không tồn tại.")
        try:
            from app.adapters.ffmpeg_adapter import probe_video

            media = probe_video(str(path))
        except Exception as exc:
            raise DouyinDownloaderError(f"File tải về không có luồng video hợp lệ: {path.name}.") from exc
        if media.width <= 0 or media.height <= 0 or media.duration <= 0:
            raise DouyinDownloaderError(f"File tải về không phải video xem được: {path.name}.")

    def _upsert_output(self, job: _DownloadJob, result: dict[str, Any]) -> None:
        normalized = self._normalize_link(str(result.get("link") or ""))
        for index, item in enumerate(job.outputs):
            if self._normalize_link(str(item.get("link") or "")) == normalized:
                job.outputs[index] = result
                self._refresh_job_counts(job)
                return
        job.outputs.append(result)
        self._refresh_job_counts(job)

    def _refresh_job_counts(self, job: _DownloadJob) -> None:
        success_statuses = {"success", "skipped"}
        job.completed_items = sum(1 for item in job.outputs if item.get("status") in success_statuses)
        job.failed_items = sum(1 for item in job.outputs if item.get("status") == "failed")
        job.total_items = max(job.total_items, len(job.links))

    def _job_progress_from_outputs(self, job: _DownloadJob) -> int:
        total = max(1, job.total_items or len(job.links))
        processed = min(total, len({self._normalize_link(str(item.get("link") or "")) for item in job.outputs if item.get("status") in {"success", "skipped", "failed"}}))
        return int((processed / total) * 100)

    def _remaining_download_links(self, job: _DownloadJob) -> list[str]:
        done = {
            self._normalize_link(str(item.get("link") or ""))
            for item in job.outputs
            if item.get("status") in {"success", "skipped"}
        }
        return [link for link in job.links if self._normalize_link(link) not in done]

    def _mark_job_paused(self, job: _DownloadJob) -> None:
        if job.job_type == "scan":
            job.status = "paused"
            job.pause_requested = False
            job.completed_items = len(job.links)
            job.total_items = len(job.links)
            job.progress = max(0, min(99, int(job.progress)))
            job.current_step = "Đã dừng quét, có thể dùng các link đã tìm được"
            job.log("Đã dừng quét an toàn. Danh sách hiện tại vẫn được giữ lại để tải nếu cần.")
            job.touch()
            self._save_job(job)
            return
        self._refresh_job_counts(job)
        job.status = "paused"
        job.pause_requested = False
        job.progress = self._job_progress_from_outputs(job)
        job.current_step = "Đã dừng tải, có thể tiếp tục sau"
        job.log("Đã dừng tải an toàn. Bấm Tiếp tục tải để tải các video còn lại.")
        job.touch()
        self._save_job(job)

    def _create_job(self, job_type: str) -> _DownloadJob:
        job = _DownloadJob(job_id=str(uuid.uuid4()), job_type=job_type)
        with self._jobs_lock:
            self._jobs[job.job_id] = job
            self._jobs = dict(list(self._jobs.items())[-100:])
        self._save_job(job)
        return job

    def _must_get_job(self, job_id: str) -> _DownloadJob:
        with self._jobs_lock:
            job = self._jobs.get(job_id)
        if not job:
            raise DouyinDownloaderError("Không tìm thấy tác vụ tải Douyin.")
        return job

    def _require_browser(self) -> Any:
        if not self._driver:
            raise DouyinDownloaderError("Bạn cần bấm “Mở Chrome Douyin” và đăng nhập Douyin trước.")
        return self._driver

    def _find_cached_chromedriver(self) -> str | None:
        for pattern in ("**/chromedriver.exe", "**/chromedriver"):
            for file in self.driver_cache_dir.glob(pattern):
                if file.is_file():
                    return str(file.resolve())
        return None

    def _import_selenium(self):
        try:
            from selenium import webdriver  # type: ignore
            from selenium.webdriver.chrome.service import Service  # type: ignore
        except Exception as exc:
            raise DouyinDownloaderError(
                "Backend chưa có Selenium. Hãy cài requirements hoặc dùng bản exe release đã đóng gói Selenium."
            ) from exc
        return webdriver, Service

    def _import_wait_tools(self):
        try:
            from selenium.webdriver.common.by import By  # noqa: F401
            from selenium.webdriver.support import expected_conditions as EC  # noqa: F401
            from selenium.webdriver.support.ui import WebDriverWait  # noqa: F401
        except Exception as exc:
            raise DouyinDownloaderError("Thiếu thư viện hỗ trợ chờ trang của Selenium.") from exc

    def _wait_for_body(self, driver: Any, timeout: int = 15) -> None:
        from selenium.webdriver.common.by import By  # type: ignore
        from selenium.webdriver.support import expected_conditions as EC  # type: ignore
        from selenium.webdriver.support.ui import WebDriverWait  # type: ignore

        WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    def _has_login_cookie(self, cookies: list[dict[str, Any]]) -> bool:
        names = {str(cookie.get("name") or "").lower() for cookie in cookies}
        return bool(names.intersection(LOGIN_COOKIE_NAMES))

    def _clean_links(self, links: list[str]) -> list[str]:
        seen: set[str] = set()
        cleaned: list[str] = []
        for link in links:
            normalized = self._normalize_link(link)
            if not normalized or normalized in seen:
                continue
            cleaned.append(normalized)
            seen.add(normalized)
        return cleaned

    def _normalize_link(self, link: str) -> str:
        cleaned = str(link).strip()
        if not cleaned:
            return ""
        return cleaned.split("?")[0]

    def _safe_filename(self, value: str) -> str:
        cleaned = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", value)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ._-")
        return cleaned[:90] or f"douyin_{int(time.time())}"

    def _user_agent(self) -> str:
        try:
            driver = self._driver
            if driver:
                return str(driver.execute_script("return navigator.userAgent") or "")
        except Exception:
            pass
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari/537.36"
