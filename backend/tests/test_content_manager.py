from __future__ import annotations

import json
from pathlib import Path

from app import database
from app.modules.content_manager.content_service import ContentService


def test_content_service_builds_items_and_preserves_manual_edits(tmp_path):
    project_id, output_dir, script_path = _seed_project_with_output(tmp_path)
    service = ContentService()

    items = service.get_content_items(project_id)

    assert len(items) == 1
    assert items[0].caption == "Caption AI ban đầu"
    assert items[0].hashtags == ["#review", "#sanpham"]
    assert items[0].timeline_template_id == "ugc_reviewer_natural"

    service.update_content_item(
        project_id,
        1,
        {
            "caption": "Caption đã sửa thủ công",
            "hashtags": "#manual #caption",
            "publish_status": "copied",
            "user_note": "Đăng TikTok trước",
        },
    )
    script_path.write_text(
        json.dumps(_script(caption="Caption AI mới", hook="Hook mới", hashtags=["#new"]), ensure_ascii=False),
        encoding="utf-8",
    )

    rebuilt = service.build_content_items_from_outputs(project_id)

    assert rebuilt[0].caption == "Caption đã sửa thủ công"
    assert rebuilt[0].hashtags == ["#manual", "#caption"]
    assert rebuilt[0].publish_status.value == "copied"
    assert rebuilt[0].user_note == "Đăng TikTok trước"
    assert rebuilt[0].hook == "Hook mới"
    assert (output_dir / "content_items.json").exists()


def _seed_project_with_output(tmp_path: Path) -> tuple[str, Path, Path]:
    database.DB_PATH = tmp_path / "content-manager.db"
    database.init_db()
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir()
    output_dir.mkdir()

    project_id = "project-content"
    database.create_project(project_id, _config(source_dir, output_dir))
    script_path = output_dir / "video_001_script.json"
    script_path.write_text(json.dumps(_script(), ensure_ascii=False), encoding="utf-8")
    timeline_path = output_dir / "video_001_timeline.json"
    timeline_path.write_text(
        json.dumps({"template_id": "ugc_reviewer_natural"}, ensure_ascii=False),
        encoding="utf-8",
    )
    video_path = output_dir / "video_001.mp4"
    video_path.write_bytes(b"video")

    database.create_job("job-content", project_id, preview_only=False, total_outputs=1)
    database.update_job(
        "job-content",
        status="completed",
        output_folder=str(output_dir),
        results_json=json.dumps(
            {
                "outputs": [
                    {
                        "index": 1,
                        "path": str(video_path),
                        "status": "success",
                        "script_file": str(script_path),
                        "timeline_file": str(timeline_path),
                        "script_variant_id": "reviewer_natural",
                    }
                ]
            },
            ensure_ascii=False,
        ),
    )
    return project_id, output_dir, script_path


def _script(
    caption: str = "Caption AI ban đầu",
    hook: str = "Hook ban đầu",
    hashtags: list[str] | None = None,
) -> dict:
    return {
        "hook": hook,
        "voiceover": [{"time_hint": "0-3s", "text": "Đây là voice."}],
        "subtitles": [{"start_hint": 0, "end_hint": 3, "text": "Đây là voice."}],
        "cta": "Xem chi tiết ngay",
        "caption": caption,
        "hashtags": hashtags or ["#review", "#sanpham"],
        "variant_style_id": "reviewer_natural",
    }


def _config(source_dir: Path, output_dir: Path) -> dict:
    return {
        "project_name": "content-test",
        "source_folder": str(source_dir),
        "output_folder": str(output_dir),
        "product": {
            "name": "Sản phẩm test",
            "brand": "Brand",
            "description": "Mô tả sản phẩm",
            "features": ["Tính năng"],
            "cta": "Xem chi tiết ngay",
        },
        "render": {
            "output_count": 1,
            "duration": 12,
            "aspect_ratio": "9:16",
            "resolution": "1080x1920",
            "fps": 30,
        },
        "effects": {
            "cut_intensity": 70,
            "speed_variation": 30,
            "grain": 0,
            "zoom_motion": 0,
            "overlay_height": 33,
            "subtitle_size": 84,
        },
        "ai": {
            "text_model": "gemini-test",
            "tone": "friendly_reviewer",
            "language": "vi",
            "gemini_api_keys": [],
        },
    }

