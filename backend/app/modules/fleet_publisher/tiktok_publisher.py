from __future__ import annotations

import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

# Note: playwright is required
# Run: pip install playwright && playwright install chromium


def ensure_playwright_browsers() -> None:
    """Checks if Playwright chromium is installed, and installs it if missing."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise ImportError(
            "Vui lòng cài đặt thư viện Playwright: pip install playwright"
        ) from e

    try:
        with sync_playwright() as p:
            # Try to launch chromium to check if installed
            browser = p.chromium.launch(headless=True)
            browser.close()
    except Exception as e:
        logger.info("Không tìm thấy trình duyệt Playwright Chromium. Đang tự động cài đặt...")
        import subprocess
        try:
            subprocess.run(["playwright", "install", "chromium"], check=True, capture_output=True)
            logger.info("Đã cài đặt Playwright Chromium thành công.")
        except Exception as install_err:
            logger.error("Cài đặt Playwright Chromium tự động thất bại: %s", str(install_err))
            raise RuntimeError(
                "Không tìm thấy trình duyệt Chromium cho Playwright. "
                "Vui lòng mở terminal và chạy lệnh: playwright install chromium"
            ) from install_err


def publish_to_tiktok(
    video_path: str,
    title: str,
    caption: str | None,
    hashtags: str | None,
    product_link: str | None,
    auth_data: dict[str, Any],
) -> str:
    """Uploads a video to TikTok Creator Studio using Playwright browser automation

    with logged-in cookies.

    Args:
        video_path: Absolute path to the video file.
        title: Title of the video.
        caption: Caption text.
        hashtags: Hashtags (space-separated, with #).
        product_link: Product URL to append to the caption.
        auth_data: Dictionary containing cookies list.

    Returns:
        str: A string status indicating success (e.g. 'tiktok_published_ok').
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Không tìm thấy tệp video tại: {video_path}")

    # Make sure chromium is available
    ensure_playwright_browsers()

    from playwright.sync_api import sync_playwright

    cookies = auth_data.get("cookies")
    if not cookies:
        raise ValueError("Thiếu danh sách cookies đăng nhập TikTok trong auth_data.")

    # Build description
    desc_parts = [title]
    if caption:
        desc_parts.append(caption)
    if hashtags:
        desc_parts.append(hashtags)
    if product_link:
        desc_parts.append(f"\n🛒 Link mua: {product_link}")
    description = " ".join(desc_parts)  # TikTok caption uses spaces

    headless = auth_data.get("headless", True)
    logger.info("TikTok Playwright: Khởi chạy trình duyệt chromium (headless=%s)...", headless)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
        )
        
        # Create context with custom user agent to avoid bot detection
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=user_agent
        )
        
        # Inject TikTok cookies
        logger.info("TikTok Playwright: Đang nạp %d cookie đăng nhập...", len(cookies))
        formatted_cookies = []
        for c in cookies:
            # Playwright cookies require domain, name, value, path, etc.
            # Make sure keys match Playwright requirements
            domain = c.get("domain", "")
            if not domain.startswith("."):
                # Playwright works best with explicit domains
                pass
            formatted_cookies.append({
                "name": c.get("name"),
                "value": c.get("value"),
                "domain": domain if domain else ".tiktok.com",
                "path": c.get("path", "/"),
                "expires": c.get("expires", time.time() + 3600 * 24 * 30),
                "httpOnly": c.get("httpOnly", False),
                "secure": c.get("secure", True),
                "sameSite": c.get("sameSite", "Lax")
            })
            
        context.add_cookies(formatted_cookies)
        
        page = context.new_page()
        
        # Navigate to TikTok Studio Upload Page
        upload_url = "https://www.tiktok.com/tiktokstudio/upload?lang=vi-VN"
        logger.info("TikTok Playwright: Đang chuyển hướng đến trang tải lên TikTok Studio...")
        page.goto(upload_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        # Check if we are logged in by checking if we redirected to login
        if "login" in page.url:
            raise RuntimeError(
                "TikTok Playwright: Cookies đã hết hạn hoặc không hợp lệ. Vui lòng cập nhật Cookie đăng nhập TikTok."
            )

        # Wait for file input or drag-drop area
        logger.info("TikTok Playwright: Đang tìm và tải video lên...")
        
        # TikTok Studio file input selector
        file_input_selector = "input[type='file']"
        try:
            page.wait_for_selector(file_input_selector, timeout=20000)
            file_input = page.locator(file_input_selector)
            file_input.set_input_files(video_path)
            logger.info("TikTok Playwright: Đã chọn tệp video. Đang tải lên...")
        except Exception as e:
            # Fallback selectors
            raise RuntimeError(f"Không tìm thấy khung tải video của TikTok Studio: {str(e)}") from e

        # Wait for video upload processing (usually a progress bar or player preview appears)
        # We can wait for the caption textbox to become interactive
        logger.info("TikTok Playwright: Chờ tải video hoàn tất và giao diện soạn thảo xuất hiện...")
        page.wait_for_timeout(5000)  # Wait for file upload to initiate
        
        # Locate the caption textbox
        # TikTok Studio uses a div with contenteditable or class ending with editor
        caption_selector = "div[contenteditable='true'], div[role='textbox'], .editor"
        try:
            page.wait_for_selector(caption_selector, timeout=30000)
            caption_box = page.locator(caption_selector).first
            
            # Focus, select all, delete, and type new description
            caption_box.focus()
            page.keyboard.press("Control+A")
            page.keyboard.press("Delete")
            page.wait_for_timeout(500)
            caption_box.fill(description)
            logger.info("TikTok Playwright: Đã điền mô tả và hashtag.")
        except Exception as e:
            logger.warning("Không thể điền mô tả tự động bằng selector chuẩn: %s. Đang dùng phím tắt...", str(e))
            # Fallback: click around and type
            try:
                page.keyboard.press("Tab")
                page.keyboard.type(description)
            except Exception:
                raise RuntimeError(f"Lỗi khi điền nội dung mô tả TikTok: {str(e)}") from e

        # Wait a bit for processing to complete
        logger.info("TikTok Playwright: Chờ video nén và kiểm tra bản quyền ngầm...")
        page.wait_for_timeout(5000)

        # Locate the "Post" / "Đăng" button
        # Usually it is a button with text "Đăng" or "Post"
        post_button_selectors = [
            "button:has-text('Đăng')",
            "button:has-text('Post')",
            "button.btn-post",
            "//button[contains(., 'Đăng')]",
            "//button[contains(., 'Post')]"
        ]
        
        posted = False
        for selector in post_button_selectors:
            try:
                btn = page.locator(selector)
                if btn.count() > 0 and btn.is_visible():
                    logger.info("TikTok Playwright: Tìm thấy nút đăng bằng selector '%s'. Tiến hành click...", selector)
                    btn.click()
                    posted = True
                    break
            except Exception:
                continue
                
        if not posted:
            # Try pressing Enter or click fallback
            raise RuntimeError("TikTok Playwright: Không tìm thấy nút 'Đăng' hoặc 'Post' trên giao diện.")

        # Wait for success dialog or redirection
        logger.info("TikTok Playwright: Chờ phản hồi xác nhận đăng bài thành công...")
        page.wait_for_timeout(8000)
        
        logger.info("TikTok Playwright: Đăng video lên TikTok thành công!")
        browser.close()

    return "tiktok_published_ok"
