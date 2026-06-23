from __future__ import annotations

import re

from app.modules.silent_visual_tagging.visual_tag_schema import TAG_CATEGORY_BY_NAME, VisualTag


SOURCE_CONFIDENCE = {
    "product_context": 0.90,
    "ocr_text": 0.80,
    "folder_name": 0.65,
    "filename": 0.65,
    "segment_type": 0.70,
    "visual_rule": 0.50,
    "user": 1.00,
}


KEYWORD_GROUPS: list[tuple[list[str], list[str]]] = [
    (["厨房", "厨具", "锅", "碗", "杯", "水槽", "冰箱", "收纳盒", "厨房好物", "菜板", "油污", "洗碗", "bếp", "nhà bếp", "dụng cụ bếp", "kitchen"], ["kitchen_goods", "kitchen_scene"]),
    (["收纳", "整理", "置物架", "架子", "抽屉", "衣柜", "空间", "storage", "organize", "sắp xếp", "gọn gàng", "kệ", "hộp đựng"], ["storage_organization", "storage_scene", "organizing"]),
    (["桌面", "书桌", "办公", "键盘", "鼠标", "显示器", "学习", "desk", "setup", "bàn học", "bàn làm việc", "góc làm việc"], ["desk_setup", "desk_scene"]),
    (["清洁", "擦", "拖把", "扫", "污渍", "除尘", "clean", "lau", "dọn", "vệ sinh", "bụi", "bẩn"], ["cleaning_goods", "cleaning_scene", "cleaning", "wiping"]),
    (["美妆", "护肤", "化妆", "粉扑", "镜子", "口红", "美容", "makeup", "skincare", "làm đẹp", "trang điểm"], ["beauty_goods", "vanity_scene"]),
    (["宿舍", "学生", "寝室", "小房间", "dorm", "ký túc xá", "phòng nhỏ", "sinh viên"], ["dorm_goods", "dorm_scene"]),
    (["家居", "家用", "客厅", "卧室", "home goods", "gia dụng", "góc nhà", "phòng khách", "phòng ngủ"], ["home_goods", "home_scene"]),
    (["开箱", "拆箱", "拆包", "包装", "盒子", "unbox", "mở hộp", "đập hộp", "bao bì"], ["unboxing", "opening_package", "packaging"]),
    (["测评", "试用", "使用", "效果", "对比", "推荐", "review", "test", "demo", "dùng thử", "trải nghiệm", "hiệu quả", "so sánh"], ["usage_demo", "testing", "result_showcase", "comparison"]),
]

NOISE_PHRASES = (
    "小米同学",
    "小米同學",
    "抖音",
    "douyin",
    "tiktok",
    "小红书",
    "小紅書",
    "关注",
    "關注",
    "点赞",
    "點贊",
    "评论",
    "評論",
    "收藏",
    "直播",
    "同款",
    "链接",
    "連結",
)


class KeywordTagMapper:
    def tags_from_text(self, text: str, source: str) -> list[VisualTag]:
        normalized = _normalize_signal_text(text)
        if not normalized:
            return []
        confidence = SOURCE_CONFIDENCE.get(source, 0.5)
        found: dict[str, VisualTag] = {}
        for keywords, tags in KEYWORD_GROUPS:
            matches = [keyword for keyword in keywords if keyword.casefold() in normalized]
            if not matches:
                continue
            reason = f"Matched keyword: {matches[0]}"
            for tag in tags:
                found[tag] = VisualTag(
                    tag=tag,
                    category=TAG_CATEGORY_BY_NAME[tag],
                    confidence=confidence,
                    source=source,
                    reason=reason,
                )
        return list(found.values())


def _normalize_signal_text(text: str) -> str:
    normalized = str(text or "").casefold().replace("_", " ").replace("-", " ")
    normalized = re.sub(r"https?://\S+|www\.\S+", " ", normalized)
    normalized = re.sub(r"@[a-z0-9_.-]+", " ", normalized)
    normalized = normalized.replace("#", " ")
    for phrase in NOISE_PHRASES:
        normalized = normalized.replace(phrase.casefold(), " ")
    return " ".join(normalized.split())
