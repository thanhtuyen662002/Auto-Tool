from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Note: google-api-python-client and google-auth-oauthlib are required
# Run: pip install google-api-python-client google-auth-oauthlib


def publish_to_youtube(
    video_path: str,
    title: str,
    caption: str | None,
    hashtags: str | None,
    product_link: str | None,
    auth_data: dict[str, Any],
) -> str:
    """Uploads a video to YouTube as a Short, appends the product link to the description

    as a fallback, and posts a comment containing the product link.

    Args:
        video_path: Absolute path to the video file.
        title: Video title (max 100 chars).
        caption: Video description/caption.
        hashtags: Video hashtags.
        product_link: Product link to include in description and comment.
        auth_data: OAuth2 credentials dictionary.

    Returns:
        str: The uploaded YouTube Video ID.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Không tìm thấy tệp video tại: {video_path}")

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError as e:
        logger.error("Thiếu thư viện googleapiclient hoặc google-auth. Vui lòng cài đặt: %s", str(e))
        raise ImportError(
            "Vui lòng cài đặt thư viện YouTube API: pip install google-api-python-client google-auth-oauthlib"
        ) from e

    # Build description combining caption, hashtags, and product link fallback
    desc_parts = []
    if caption:
        desc_parts.append(caption)
    if hashtags:
        desc_parts.append(hashtags)
    if product_link:
        desc_parts.append(f"\n🛒 Link sản phẩm: {product_link}")
    description = "\n".join(desc_parts)

    # Clean up title for YouTube Shorts (max 100 chars)
    clean_title = title[:100]

    # Initialize credentials
    try:
        credentials = Credentials(
            token=auth_data.get("token"),
            refresh_token=auth_data.get("refresh_token"),
            token_uri=auth_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=auth_data.get("client_id"),
            client_secret=auth_data.get("client_secret"),
            scopes=auth_data.get("scopes", ["https://www.googleapis.com/auth/youtube.upload"]),
        )
    except Exception as e:
        raise ValueError(f"Dữ liệu xác thực tài khoản YouTube không hợp lệ: {str(e)}") from e

    # Build the YouTube service client
    try:
        youtube = build("youtube", "v3", credentials=credentials)
    except Exception as e:
        raise RuntimeError(f"Không thể khởi tạo kết nối YouTube API: {str(e)}") from e

    # Setup the upload body
    body = {
        "snippet": {
            "title": clean_title,
            "description": description,
            "tags": [t.strip("# ") for t in hashtags.split()] if hashtags else [],
            "categoryId": "22",  # People & Blogs
        },
        "status": {
            "privacyStatus": auth_data.get("privacy_status", "public"),  # 'public', 'private', 'unlisted'
            "selfDeclaredMadeForKids": False,
        },
    }

    # Upload video file
    logger.info("Đang tải video lên YouTube: %s", video_path)
    media = MediaFileUpload(
        video_path, mimetype="video/mp4", chunksize=1024 * 1024, resumable=True
    )
    
    try:
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.info("Tiến trình tải YouTube: %d%%", int(status.progress() * 100))
        
        video_id = response.get("id")
        if not video_id:
            raise RuntimeError("YouTube API không trả về Video ID sau khi tải lên.")
        logger.info("Tải lên YouTube thành công! Video ID: %s", video_id)

    except Exception as e:
        raise RuntimeError(f"Lỗi khi tải video lên YouTube API: {str(e)}") from e

    # Post comment containing product link if available
    if product_link:
        try:
            logger.info("Đang đăng bình luận chứa link sản phẩm lên video: %s", video_id)
            comment_text = f"🛒 Mua sản phẩm tiện ích trong video tại đây: {product_link}"
            comment_body = {
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {
                        "snippet": {
                            "textOriginal": comment_text
                        }
                    }
                }
            }
            youtube.commentThreads().insert(
                part="snippet",
                body=comment_body
            ).execute()
            logger.info("Đã đăng bình luận lên YouTube thành công.")
            # Note: The official YouTube API does not support pinning comments programmatically.
            # We rely on the comment being the top level thread and including the link in description.
        except Exception as e:
            logger.warning("Đăng bình luận lên YouTube thất bại (nhưng video đã tải lên thành công): %s", str(e))

    return video_id
