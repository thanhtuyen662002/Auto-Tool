from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from app.database import get_connection

logger = logging.getLogger(__name__)


def get_product_by_tag(tag: str) -> dict[str, Any] | None:
    """Queries the database for a product matching the given tag (case-insensitive)."""
    clean_tag = tag.strip("# ").lower()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM product_affiliates 
            WHERE lower(product_tag) = ? OR ? LIKE '%' || lower(product_tag) || '%'
            LIMIT 1
            """,
            (clean_tag, clean_tag),
        ).fetchone()
        
        if row:
            return dict(row)
            
        # Fallback: check if the tag contains the product tag
        rows = conn.execute("SELECT * FROM product_affiliates").fetchall()
        for r in rows:
            p_tag = r["product_tag"].strip("# ").lower()
            if p_tag in clean_tag or clean_tag in p_tag:
                return dict(r)
                
    return None


def match_product_links(video_path: str, tags: list[str] | None = None) -> str | None:
    """Finds a matching product affiliate link based on video tags or filename."""
    all_tags = []
    if tags:
        all_tags.extend(tags)
        
    # Extract tags from filename
    filename = os.path.basename(video_path)
    filename_tags = re.findall(r"#\w+", filename)
    if filename_tags:
        all_tags.extend(filename_tags)
        
    # Also split filename words to match tags
    clean_name = re.sub(r"[^\w\s]", " ", filename)
    words = clean_name.split()
    all_tags.extend(words)

    # De-duplicate
    seen = set()
    unique_tags = [x for x in all_tags if not (x.lower() in seen or seen.add(x.lower()))]

    # Try matching each tag to a product
    for tag in unique_tags:
        product = get_product_by_tag(tag)
        if product:
            logger.info("Đã tìm thấy link sản phẩm phù hợp dựa trên tag '%s': %s", tag, product["product_name"])
            return product["affiliate_link"]

    # Global fallback: return the first product link if available in database
    with get_connection() as conn:
        row = conn.execute("SELECT affiliate_link FROM product_affiliates LIMIT 1").fetchone()
        if row:
            logger.info("Không tìm thấy tag trùng khớp. Sử dụng link sản phẩm mặc định đầu tiên.")
            return row["affiliate_link"]

    return None


def suggest_content_for_video(
    video_path: str,
    custom_tags: list[str] | None = None,
    tone: str = "Chuyên nghiệp",
) -> tuple[str, str, str, str | None]:
    """Generates video title, caption, hashtags, and product link automatically.

    First queries the database to see if this video was processed by our reup
    pipeline.
    If so, it reuses the high-quality Vietnamese caption.
    Otherwise, it uses smart local heuristics.

    Returns:
        tuple[str, str, str, str | None]: (title, caption, hashtags, product_link)
    """
    filename = os.path.basename(video_path)
    base_name = os.path.splitext(filename)[0]
    
    # Clean up filename for a default title (strip tags and weird symbols)
    clean_title = re.sub(r"#\w+", "", base_name)  # Remove hashtags
    clean_title = re.sub(r"_+", " ", clean_title)  # Replace underscores
    clean_title = re.sub(r"\s+", " ", clean_title).strip()
    if not clean_title:
        clean_title = "Video tiện ích thông minh"

    # Default values
    title = clean_title
    caption = "Sản phẩm gia dụng thông minh tiện ích cho mọi nhà."
    hashtags = "#shorts #giadungthongminh #tienich #viral"
    product_link = None

    # Step 1: Query output_content_items to see if we have reup results
    try:
        with get_connection() as conn:
            # Query by matching video_path suffix (to handle relative/absolute path shifts)
            suffix = f"%{filename}"
            row = conn.execute(
                """
                SELECT caption, hashtags_json, hook 
                FROM output_content_items 
                WHERE video_path LIKE ? 
                LIMIT 1
                """,
                (suffix,),
            ).fetchone()
            
            if row:
                logger.info("Tìm thấy dữ liệu kịch bản gốc trong dự án cho video: %s", filename)
                db_caption = row["caption"]
                db_hook = row["hook"]
                
                try:
                    db_tags = json.loads(row["hashtags_json"])
                except Exception:
                    db_tags = []
                
                if db_hook:
                    title = db_hook[:80]  # Use hook as title (max 80 chars)
                
                caption = db_caption
                
                if db_tags:
                    hashtags = " ".join([f"#{t.strip('# ')}" for t in db_tags])
    except Exception as db_err:
        logger.warning("Truy vấn kịch bản gốc từ database thất bại: %s", str(db_err))

    # Step 2: Extract tags for product mapping
    # Merge custom tags, database tags, and filename tags
    all_tags = []
    if custom_tags:
        all_tags.extend(custom_tags)
    
    # Extract tags from the hashtags string
    extracted_tags = re.findall(r"#(\w+)", hashtags)
    all_tags.extend(extracted_tags)
    
    # Step 3: Match product link
    product_link = match_product_links(video_path, all_tags)

    return title, caption, hashtags, product_link
