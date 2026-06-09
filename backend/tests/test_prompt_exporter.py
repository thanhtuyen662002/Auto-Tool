from __future__ import annotations

import json
from pathlib import Path

from app.modules.product_reference_prompt.prompt_exporter import PromptExporter
from app.modules.product_reference_prompt.video_prompt_generator import ProductVideoPromptGenerator
from backend.tests.prompt_pack_helpers import add_main_asset, make_project


def test_prompt_exporter_writes_all_prompt_pack_files(tmp_path: Path) -> None:
    project_id = make_project(tmp_path)
    add_main_asset(project_id, tmp_path)
    prompt_pack = ProductVideoPromptGenerator().generate_video_prompt_pack(project_id)
    output_dir = tmp_path / "outputs" / "prompt-pack-test" / "prompt_pack"

    files = PromptExporter().export_prompt_pack(prompt_pack, str(output_dir))

    expected_keys = {
        "product_reference_summary",
        "storyboard_5_scenes",
        "video_prompt_full",
        "video_prompt_short",
        "video_prompt_pack_json",
        "negative_prompt",
        "prompt_pack_generation_log",
    }
    assert set(files) == expected_keys
    for path in files.values():
        assert Path(path).exists()

    summary = json.loads((output_dir.parent / "project_summary.json").read_text(encoding="utf-8"))
    assert summary["prompt_pack"]["generated"] is True
    assert summary["prompt_pack"]["reference_assets_used"] == 1
