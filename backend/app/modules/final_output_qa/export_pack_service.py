from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from app import database
from app.modules.douyin_reup.subtitle_timing_guard import parse_srt_blocks
from app.modules.final_output_qa.final_output_qa_schema import (
    CreateExportPackRequest,
    ExportPackItem,
    PlatformExportPack,
    PlatformTarget,
)
from app.modules.final_output_qa.final_output_qa_service import FinalOutputQAService, build_final_qa_summary
from app.utils.file_utils import ensure_dir, write_json


DEFAULT_CAPTION = "Xem xong moi thay mon nay tien that."
DEFAULT_HASHTAGS = "#xuhuong #review #meohay #douyin"


class ExportPackService:
    def create_export_pack_for_job(
        self,
        job_id: str,
        platform_target: PlatformTarget,
        output_dir: str | None = None,
        *,
        copy_videos: bool = True,
        include_subtitles: bool = True,
        include_logs: bool = True,
        include_captions: bool = True,
        include_posting_checklist: bool = True,
        output_indexes: list[int] | None = None,
    ) -> PlatformExportPack:
        database.init_db()
        job = database.get_job(job_id)
        if not job:
            raise LookupError(f"Job not found: {job_id}")
        payload = job.get("results") or {}
        outputs = [item for item in (payload.get("outputs") or []) if isinstance(item, dict)]
        selected_indexes = {int(item) for item in (output_indexes or [])}
        if selected_indexes:
            outputs = [item for item in outputs if int(item.get("index") or -1) in selected_indexes]
        if not outputs:
            raise ValueError("Job has no output artifacts to export.")

        all_reports = FinalOutputQAService().run_qa_for_job(job_id, platform_target)
        job = database.get_job(job_id) or job
        payload = job.get("results") or payload
        outputs = [item for item in (payload.get("outputs") or []) if isinstance(item, dict)]
        if selected_indexes:
            outputs = [item for item in outputs if int(item.get("index") or -1) in selected_indexes]
        reports = [report for report in all_reports if not selected_indexes or _video_index(report.video_id) in selected_indexes]
        root = self._resolve_output_dir(job, platform_target, output_dir)
        videos_dir = ensure_dir(root / "videos")
        subtitles_dir = ensure_dir(root / "subtitles")
        captions_dir = ensure_dir(root / "captions")
        logs_dir = ensure_dir(root / "logs")
        qa_dir = ensure_dir(root / "qa")
        items: list[ExportPackItem] = []
        caption_rows: list[dict[str, str]] = []

        for output in outputs:
            index = int(output.get("index") or len(caption_rows) + 1)
            video_name = f"video_{index:03d}_vi_sub.mp4"
            video_path = _path(output.get("path"))
            if copy_videos and video_path and video_path.exists():
                target = videos_dir / video_name
                _copy(video_path, target)
                items.append(_item(f"video_{index:03d}_final", target, "video"))

            if include_subtitles:
                subtitle_specs = [
                    ("source_srt_file", f"video_{index:03d}_source_zh.srt", "source_subtitle"),
                    ("translated_srt_file", f"video_{index:03d}_vi.srt", "translated_subtitle"),
                    ("corrected_srt_file", f"video_{index:03d}_vi.corrected.srt", "corrected_subtitle"),
                    ("corrected_ass_file", f"video_{index:03d}_vi.corrected.ass", "ass_subtitle"),
                    ("subtitle_ass_file", f"video_{index:03d}_vi.ass", "ass_subtitle"),
                ]
                copied_names: set[str] = set()
                for key, name, file_type in subtitle_specs:
                    source = _path(output.get(key))
                    if not source or not source.exists() or name in copied_names:
                        continue
                    target = subtitles_dir / name
                    _copy(source, target)
                    copied_names.add(name)
                    items.append(_item(f"video_{index:03d}_{key}", target, file_type))

            if include_logs:
                for key, file_type in (("log_file", "log"),):
                    source = _path(output.get(key))
                    if source and source.exists():
                        target = logs_dir / source.name
                        _copy(source, target)
                        items.append(_item(f"video_{index:03d}_{key}", target, file_type))

            qa_summary = output.get("final_output_qa") or {}
            qa_path = _path(qa_summary.get("report_path")) if isinstance(qa_summary, dict) else None
            if qa_path and qa_path.exists():
                target = qa_dir / f"video_{index:03d}_final_qa.json"
                _copy(qa_path, target)
                items.append(_item(f"video_{index:03d}_qa", target, "qa_report"))

            caption, hashtags = _caption_for_output(output)
            caption_rows.append(
                {
                    "filename": video_name,
                    "caption": caption,
                    "hashtags": hashtags,
                    "qa_status": str(qa_summary.get("status") or "not_checked") if isinstance(qa_summary, dict) else "not_checked",
                    "qa_score": str(qa_summary.get("score") or "") if isinstance(qa_summary, dict) else "",
                    "notes": _qa_notes(qa_summary),
                }
            )

        summary = build_final_qa_summary(reports, platform_target)
        qa_summary_path = qa_dir / "final_qa_summary.json"
        write_json(qa_summary_path, summary)
        items.append(_item("final_qa_summary", qa_summary_path, "qa_summary"))

        source_summary = _path((payload.get("summary") or {}).get("summary_file"))
        if include_logs and source_summary and source_summary.exists():
            target = logs_dir / "douyin_reup_summary.json"
            _copy(source_summary, target)
            items.append(_item("douyin_reup_summary", target, "log"))

        caption_txt_path: Path | None = None
        caption_csv_path: Path | None = None
        if include_captions:
            caption_txt_path = captions_dir / "captions.txt"
            caption_txt_path.write_text(_caption_txt(caption_rows), encoding="utf-8")
            caption_csv_path = captions_dir / "captions.csv"
            with caption_csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=["filename", "caption", "hashtags", "qa_status", "qa_score", "notes"])
                writer.writeheader()
                writer.writerows(caption_rows)
            items.extend([_item("captions_txt", caption_txt_path, "caption"), _item("captions_csv", caption_csv_path, "caption")])

        checklist_path: Path | None = None
        if include_posting_checklist:
            checklist_path = root / "posting_checklist.md"
            checklist_path.write_text(_posting_checklist(platform_target, items), encoding="utf-8")
            items.append(_item("posting_checklist", checklist_path, "checklist"))

        created_at = _now()
        manifest_path = root / "export_manifest.json"
        export_pack = PlatformExportPack(
            id=str(uuid.uuid4()),
            job_id=job_id,
            project_id=job.get("project_id"),
            platform_target=platform_target,
            output_dir=str(root),
            items=items,
            caption_txt_path=str(caption_txt_path) if caption_txt_path else None,
            caption_csv_path=str(caption_csv_path) if caption_csv_path else None,
            posting_checklist_path=str(checklist_path) if checklist_path else None,
            qa_summary_path=str(qa_summary_path),
            manifest_path=str(manifest_path),
            created_at=created_at,
        )
        write_json(manifest_path, export_pack.model_dump(mode="json"))
        export_pack = export_pack.model_copy(update={"items": [*items, _item("export_manifest", manifest_path, "manifest")]})

        refreshed = database.get_job(job_id) or job
        refreshed_payload = dict(refreshed.get("results") or {})
        refreshed_payload["export_pack"] = export_pack.model_dump(mode="json")
        database.update_job(job_id, results_json=json.dumps(refreshed_payload, ensure_ascii=False))
        return export_pack

    def get_export_pack_for_job(self, job_id: str) -> PlatformExportPack:
        database.init_db()
        job = database.get_job(job_id)
        if not job:
            raise LookupError(f"Job not found: {job_id}")
        payload = (job.get("results") or {}).get("export_pack")
        if not payload:
            raise LookupError(f"Export pack not found for job: {job_id}")
        return PlatformExportPack.model_validate(payload)

    def open_export_pack_folder(self, job_id: str) -> str:
        pack = self.get_export_pack_for_job(job_id)
        path = Path(pack.output_dir).expanduser().resolve()
        if not path.exists() or not path.is_dir():
            raise LookupError(f"Export pack folder not found: {path}")
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys_platform() == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
        return str(path)

    @staticmethod
    def _resolve_output_dir(job: dict, platform_target: PlatformTarget, output_dir: str | None) -> Path:
        if output_dir:
            return ensure_dir(Path(output_dir).expanduser().resolve())
        output_root = Path(job.get("output_folder") or Path.cwd()).expanduser().resolve()
        return ensure_dir(output_root / "export_pack" / platform_target.value)


def _caption_for_output(output: dict) -> tuple[str, str]:
    subtitle = _path(output.get("corrected_srt_file") or output.get("translated_srt_file") or output.get("source_srt_file"))
    if subtitle and subtitle.exists():
        try:
            blocks = parse_srt_blocks(str(subtitle))
            texts = [" ".join(block.text.split()) for block in blocks if block.text.strip()][:2]
            caption = " ".join(texts).strip()
            if caption:
                return caption[:220], DEFAULT_HASHTAGS
        except (OSError, ValueError):
            pass
    return DEFAULT_CAPTION, DEFAULT_HASHTAGS


def _caption_txt(rows: list[dict[str, str]]) -> str:
    sections = []
    for row in rows:
        sections.append(f"{row['filename']}\n\nCaption:\n{row['caption']}\n\nHashtags:\n{row['hashtags']}\n\n---")
    return "\n\n".join(sections) + "\n"


def _posting_checklist(platform_target: PlatformTarget, items: list[ExportPackItem]) -> str:
    final_video = next((item.path for item in items if item.file_type == "video"), "")
    subtitle = next((item.path for item in items if item.file_type == "corrected_subtitle"), "")
    qa_report = next((item.path for item in items if item.file_type == "qa_report"), "")
    return f"""# Posting Checklist

Platform target: {platform_target.value}

## Before posting

- [ ] Xem lại video final từ đầu đến cuối
- [ ] Kiểm tra phụ đề tiếng Việt có đúng nghĩa không
- [ ] Kiểm tra phụ đề không che nội dung quan trọng
- [ ] Kiểm tra âm lượng không quá nhỏ/quá to
- [ ] Kiểm tra nhạc nền có quyền sử dụng
- [ ] Kiểm tra quyền sử dụng video nguồn
- [ ] Kiểm tra caption không chứa claim sai
- [ ] Kiểm tra nền tảng đăng phù hợp

## Files

- Final video: {final_video}
- Corrected subtitle: {subtitle}
- QA report: {qa_report}
"""


def _qa_notes(summary) -> str:
    if not isinstance(summary, dict):
        return ""
    issues = summary.get("issues") or []
    return "; ".join(str(item.get("message") or "") for item in issues if isinstance(item, dict))


def _path(value) -> Path | None:
    if not value:
        return None
    try:
        return Path(str(value)).expanduser().resolve()
    except OSError:
        return None


def _video_index(video_id: str | None) -> int:
    if not video_id:
        return -1
    try:
        return int(video_id.rsplit("_", 1)[-1])
    except ValueError:
        return -1


def _copy(source: Path, target: Path) -> None:
    ensure_dir(target.parent)
    if source != target:
        shutil.copy2(source, target)


def _item(label: str, path: Path, file_type: str) -> ExportPackItem:
    return ExportPackItem(label=label, path=str(path), file_type=file_type, exists=path.exists())


def sys_platform() -> str:
    import sys

    return sys.platform


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()
