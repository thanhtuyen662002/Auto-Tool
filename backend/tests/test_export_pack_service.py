import json
from pathlib import Path

from app import database
from app.modules.final_output_qa.export_pack_service import ExportPackService
from app.modules.final_output_qa.final_output_qa_schema import PlatformTarget
from tests.final_output_qa_helpers import make_video


def test_export_pack_creates_folders_manifest_captions_and_checklist(tmp_path):
    database.DB_PATH = tmp_path / "export-pack.db"
    database.init_db()
    project_id = "project-export"
    job_id = "job-export"
    database.create_project(project_id, {"project_name": "export-test"})
    database.create_job(job_id, project_id, preview_only=False, total_outputs=1)
    output_root = tmp_path / "outputs"
    output_root.mkdir()
    video = make_video(output_root / "video.mp4")
    srt = output_root / "video_vi.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nMon nay dung tien.\n", encoding="utf-8")
    log = output_root / "video_001_log.json"
    log.write_text("{}", encoding="utf-8")
    summary_file = output_root / "douyin_reup_summary.json"
    summary_file.write_text("{}", encoding="utf-8")
    outputs = [{"index": 1, "path": str(video), "status": "success", "source_video": str(video), "translated_srt_file": str(srt), "log_file": str(log), "warnings": [], "errors": []}]
    database.update_job(job_id, output_folder=str(output_root), results_json=json.dumps({"summary": {"summary_file": str(summary_file)}, "outputs": outputs}))

    pack = ExportPackService().create_export_pack_for_job(job_id, PlatformTarget.tiktok)

    root = Path(pack.output_dir)
    assert (root / "videos").is_dir()
    assert (root / "subtitles").is_dir()
    assert (root / "captions" / "captions.csv").exists()
    assert (root / "captions" / "captions.txt").exists()
    assert (root / "qa" / "final_qa_summary.json").exists()
    assert (root / "posting_checklist.md").exists()
    manifest = json.loads((root / "export_manifest.json").read_text(encoding="utf-8"))
    assert manifest["platform_target"] == "tiktok"
    assert any(item["file_type"] == "video" for item in manifest["items"])
