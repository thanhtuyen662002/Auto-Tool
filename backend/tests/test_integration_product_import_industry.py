from __future__ import annotations

from pathlib import Path

from app.config import load_project_config
from app.modules.industry_presets.industry_preset_service import IndustryPresetService
from app.modules.product_import import ProductImportService, RawProductInput


PACK_DIR = Path(__file__).resolve().parents[2] / "examples" / "real_product_test_pack"


def test_product_import_to_industry_apply_keeps_product_info_and_sets_defaults() -> None:
    input_path = PACK_DIR / "product_inputs" / "projector_kaw_xmax10.txt"
    imported = ProductImportService().import_product_info(
        RawProductInput(
            input_type="txt",
            file_path=str(input_path),
            file_content=input_path.read_text(encoding="utf-8"),
            source_name=input_path.name,
        )
    )
    assert imported.success
    assert imported.product is not None
    assert imported.product.industry_preset_id == "tech_electronics"

    config = load_project_config(str(PACK_DIR / "configs" / "projector_kaw_xmax10.json"))
    original_product = config.product
    service = IndustryPresetService()
    updated = service.apply_preset_to_config(config, "tech_electronics")
    preset = service.get_preset("tech_electronics")

    assert updated.product == original_product
    assert updated.industry is not None
    assert updated.industry.preset_id == preset.id
    assert updated.visual_style.preset_id == preset.visual_style_preset_id
    assert updated.timeline.template_id == preset.timeline_template_id
    assert updated.tts.voice == preset.default_tts_voice
    assert updated.script_variation.mode == preset.script_variation_mode
    assert updated.script_variation.preferred_variant_ids == preset.preferred_script_variant_ids
