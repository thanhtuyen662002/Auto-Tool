from __future__ import annotations

import json
from pathlib import Path

from app import database
from app.modules.final_output_qa import PlatformTarget
from app.modules.final_output_qa.export_pack_service import ExportPackService


def test_v1_export_pack_creates_manifest_for_rendered_job(tmp_path: Path) -> None:
    database.DB_PATH = tmp_path / "export-pack.db"
    database.init_db()
    output_root = tmp_path / "outputs"
    video = output_root / "video_001" / "douyin_001.mp4"
    subtitle = output_root / "video_001" / "video_001_vi.srt"
    log = output_root / "video_001" / "video_001_log.json"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"fake mp4")
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nXin chào\n", encoding="utf-8")
    log.write_text('{"status":"success"}', encoding="utf-8")

    database.create_project("project-export", {"project_name": "export"})
    database.create_job("job-export", "project-export", preview_only=False, total_outputs=1)
    database.update_job(
        "job-export",
        status="completed",
        output_folder=str(output_root),
        results_json=json.dumps(
            {
                "outputs": [
                    {
                        "index": 1,
                        "status": "success",
                        "path": str(video),
                        "translated_srt_file": str(subtitle),
                        "log_file": str(log),
                    }
                ]
            },
            ensure_ascii=False,
        ),
    )

    pack = ExportPackService().create_export_pack_for_job("job-export", PlatformTarget.tiktok)

    assert Path(pack.manifest_path or "").exists()
    assert any(item.file_type == "manifest" for item in pack.items)
    assert any(item.file_type == "caption" for item in pack.items)
