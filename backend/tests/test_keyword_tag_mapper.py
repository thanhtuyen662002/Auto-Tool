from app.modules.silent_visual_tagging.keyword_tag_mapper import KeywordTagMapper


def _names(text: str) -> set[str]:
    return {tag.tag for tag in KeywordTagMapper().tags_from_text(text, "ocr_text")}


def test_chinese_kitchen_keyword_maps_to_kitchen_tags():
    assert {"kitchen_goods", "kitchen_scene"} <= _names("厨房好物推荐")


def test_chinese_storage_keyword_maps_to_storage_tags():
    assert {"storage_organization", "storage_scene", "organizing"} <= _names("沉浸式收纳整理")


def test_chinese_desk_keyword_maps_to_desk_tags():
    assert {"desk_setup", "desk_scene"} <= _names("桌面学习 setup")


def test_platform_noise_is_ignored_but_product_keyword_remains():
    names = _names("#厨房好物 小米同学 抖音 @shop")

    assert {"kitchen_goods", "kitchen_scene"} <= names
