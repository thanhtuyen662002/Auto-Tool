from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import create_app


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
