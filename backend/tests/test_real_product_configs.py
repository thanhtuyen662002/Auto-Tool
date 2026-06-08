from __future__ import annotations

import json
from pathlib import Path

from app.config import load_project_config
from app.modules.product_import import ProductImportService, RawProductInput


PACK_DIR = Path(__file__).resolve().parents[2] / "examples" / "real_product_test_pack"


def test_real_product_pack_configs_validate_and_point_to_media_dirs() -> None:
    expected = {
        "projector_kaw_xmax10.json": ("tech_electronics", "tech_dark_neon"),
        "handheld_fan_jisulife.json": ("home_lifestyle", "clean_review_light"),
        "sunscreen_jacket_guno.json": ("fashion_accessories", "fashion_minimal"),
        "home_gadget_generic.json": ("home_lifestyle", "clean_review_light"),
    }

    for filename, (industry_id, visual_style_id) in expected.items():
        config = load_project_config(str(PACK_DIR / "configs" / filename))

        assert Path(config.source_folder).exists(), filename
        assert config.render.output_count == 3
        assert config.render.aspect_ratio == "9:16"
        assert config.source_media.respect_user_exclusions is True
        assert config.source_media.prefer_favorite_segments is True
        assert config.source_media.allow_excluded_fallback is False
        assert config.industry is not None
        assert config.industry.preset_id == industry_id
        assert config.visual_style.preset_id == visual_style_id


def test_real_product_inputs_import_with_expected_industry_suggestions() -> None:
    expected = {
        "projector_kaw_xmax10.txt": {"tech_electronics"},
        "handheld_fan_jisulife.txt": {"general_product", "home_lifestyle"},
        "sunscreen_jacket_guno.txt": {"fashion_accessories"},
        "home_gadget_generic.txt": {"home_lifestyle"},
    }

    service = ProductImportService()
    for filename, allowed_industries in expected.items():
        path = PACK_DIR / "product_inputs" / filename
        text = path.read_text(encoding="utf-8")
        result = service.import_product_info(
            RawProductInput(
                input_type="txt",
                file_path=str(path),
                file_content=text,
                source_name=filename,
            )
        )

        assert result.success, json.dumps([issue.model_dump() for issue in result.issues], ensure_ascii=False)
        assert result.product is not None
        assert result.product.name
        assert result.product.features
        assert result.product.industry_preset_id in allowed_industries
