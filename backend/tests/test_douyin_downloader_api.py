from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import create_app
from app.modules.douyin_downloader.downloader_service import DouyinDownloaderService


def test_douyin_downloader_status_available_without_browser() -> None:
    client = TestClient(create_app())

    response = client.get("/api/douyin-downloader/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["browser_open"] is False
    assert payload["logged_in"] is False
    assert payload["profile_dir"]
    assert "Trình duyệt Douyin chưa mở" in payload["message"]


def test_douyin_downloader_history_available_without_browser() -> None:
    client = TestClient(create_app())

    response = client.get("/api/douyin-downloader/history")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["recent_channel_urls"], list)
    assert isinstance(payload["recent_output_folders"], list)
    assert isinstance(payload["recent_jobs"], list)
    assert isinstance(payload["downloaded_links"], dict)


def test_douyin_downloader_scan_requires_open_browser() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/douyin-downloader/scan",
        json={"channel_url": "https://www.douyin.com/", "max_scrolls": 1},
    )

    assert response.status_code == 400
    assert "đăng nhập Douyin" in response.json()["detail"]


def test_douyin_downloader_unknown_job_returns_404() -> None:
    client = TestClient(create_app())

    response = client.get("/api/douyin-downloader/jobs/missing-job")

    assert response.status_code == 404
    assert "Không tìm thấy tác vụ tải Douyin" in response.json()["detail"]


def test_douyin_downloader_scrolls_internal_feed_container(tmp_path) -> None:
    class FakeDriver:
        def __init__(self) -> None:
            self.scripts: list[str] = []

        def execute_script(self, script: str):
            self.scripts.append(script)
            return {"scrolled": True, "scrollableCount": 3, "targetTag": "DIV"}

    driver = FakeDriver()

    result = DouyinDownloaderService(data_dir=tmp_path)._scroll_channel_page(driver)

    assert result["scrolled"] is True
    assert "querySelectorAll('main" in driver.scripts[0]
    assert "WheelEvent('wheel'" in driver.scripts[0]
    assert "scrollTop" in driver.scripts[0]


def test_douyin_downloader_scroll_fallback_dispatches_wheel(tmp_path) -> None:
    class FakeDriver:
        def __init__(self) -> None:
            self.scripts: list[str] = []

        def execute_script(self, script: str):
            self.scripts.append(script)
            if len(self.scripts) == 1:
                raise RuntimeError("javascript failed")
            return None

    driver = FakeDriver()

    result = DouyinDownloaderService(data_dir=tmp_path)._scroll_channel_page(driver)

    assert result["fallback"] is True
    assert len(driver.scripts) == 2
    assert "window.scrollBy" in driver.scripts[1]
    assert "WheelEvent('wheel'" in driver.scripts[1]
