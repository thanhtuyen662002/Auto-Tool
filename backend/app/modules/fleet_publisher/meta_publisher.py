from __future__ import annotations

import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)


def publish_to_meta(
    video_path: str,
    title: str,
    caption: str | None,
    hashtags: str | None,
    product_link: str | None,
    auth_data: dict[str, Any],
) -> str:
    """Uploads a video to Facebook Reels on a Page using the Meta Graph API

    and comments with the product link.

    Args:
        video_path: Absolute path to the video file.
        title: Reel title.
        caption: Caption text.
        hashtags: Hashtags text.
        product_link: Product link to include in description and comment.
        auth_data: Page Access Token and Page ID.

    Returns:
        str: The Facebook Video ID of the published Reel.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Không tìm thấy tệp video tại: {video_path}")

    try:
        import requests
    except ImportError as e:
        logger.error("Thiếu thư viện requests. Vui lòng cài đặt: pip install requests")
        raise ImportError("Vui lòng cài đặt thư viện requests: pip install requests") from e

    page_id = auth_data.get("page_id")
    access_token = auth_data.get("access_token")

    if not page_id or not access_token:
        raise ValueError("Thiếu page_id hoặc access_token của Meta Page.")

    # Build description
    desc_parts = [title]
    if caption:
        desc_parts.append(caption)
    if hashtags:
        desc_parts.append(hashtags)
    if product_link:
        desc_parts.append(f"\n🛒 Link sản phẩm: {product_link}")
    description = "\n".join(desc_parts)

    file_size = os.path.getsize(video_path)
    api_version = auth_data.get("api_version", "v19.0")
    base_url = f"https://graph.facebook.com/{api_version}"

    # Step 1: Initialize the upload session (Start Phase)
    logger.info("Meta API: Khởi tạo phiên tải Reels lên Page: %s", page_id)
    start_url = f"{base_url}/{page_id}/video_reels"
    start_payload = {
        "upload_phase": "start",
        "access_token": access_token
    }
    
    try:
        res = requests.post(start_url, json=start_payload, timeout=30)
        res.raise_for_status()
        start_data = res.json()
        video_id = start_data.get("video_id")
        upload_url = start_data.get("upload_url")
        
        if not video_id or not upload_url:
            raise ValueError(f"Không nhận được video_id hoặc upload_url từ Meta API: {res.text}")
        logger.info("Meta API: Khởi tạo thành công. Video ID: %s", video_id)
    except Exception as e:
        raise RuntimeError(f"Lỗi khi bắt đầu phiên tải Reels lên Meta: {str(e)}") from e

    # Step 2: Upload the video file (Transfer Phase)
    logger.info("Meta API: Đang tải tệp tin nhị phân video lên server Meta (%d bytes)...", file_size)
    try:
        headers = {
            "Authorization": f"OAuth {access_token}",
            "offset": "0",
            "file_size": str(file_size),
            "Content-Type": "application/octet-stream"
        }
        
        with open(video_path, "rb") as f:
            video_data = f.read()
            
        res = requests.post(upload_url, headers=headers, data=video_data, timeout=120)
        res.raise_for_status()
        logger.info("Meta API: Tải tệp tin video lên thành công.")
    except Exception as e:
        raise RuntimeError(f"Lỗi khi truyền dữ liệu video lên Meta: {str(e)}") from e

    # Step 3: Finish and Publish (Finish Phase)
    logger.info("Meta API: Đang gửi lệnh xuất bản Reels...")
    finish_url = f"{base_url}/{page_id}/video_reels"
    finish_payload = {
        "upload_phase": "finish",
        "video_id": video_id,
        "video_state": "PUBLISHED",
        "description": description,
        "access_token": access_token
    }
    
    try:
        res = requests.post(finish_url, json=finish_payload, timeout=30)
        res.raise_for_status()
        finish_data = res.json()
        if not finish_data.get("success"):
            raise ValueError(f"Meta API báo phản hồi thất bại khi xuất bản: {res.text}")
        logger.info("Meta API: Đã xuất bản Reel thành công! Video ID: %s", video_id)
    except Exception as e:
        raise RuntimeError(f"Lỗi khi xuất bản Reels trên Meta: {str(e)}") from e

    # Step 4: Post comment containing product link
    if product_link:
        # We need to wait a few seconds for Meta to process the video before commenting,
        # or comment immediately (Meta sometimes rejects comments if video is still encoding).
        # We try to post immediately with a tiny delay.
        time.sleep(3)
        try:
            logger.info("Meta API: Đang đăng bình luận chứa link sản phẩm lên Reel: %s", video_id)
            comment_url = f"{base_url}/{video_id}/comments"
            comment_payload = {
                "message": f"🛒 Xem chi tiết và mua sản phẩm tại đây: {product_link}",
                "access_token": access_token
            }
            res = requests.post(comment_url, json=comment_payload, timeout=15)
            res.raise_for_status()
            logger.info("Meta API: Đã đăng bình luận thành công.")
        except Exception as e:
            logger.warning("Đăng bình luận lên Reels thất bại (nhưng video đã đăng thành công): %s", str(e))

    return video_id
