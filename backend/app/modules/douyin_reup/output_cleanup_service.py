from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from app.modules.douyin_reup.douyin_schema import DouyinOutputResult, DouyinReupSettings
from app.modules.douyin_reup.subtitle_timing_guard import parse_srt_blocks
from app.utils.file_utils import ensure_dir, write_json


TEMP_DIR_NAMES = {
    "frames",
    "ocr_frames",
    "_ocr_crop",
    "preview_frames",
    "temp_frames",
}
TEMP_FILE_SUFFIXES = {".tmp", ".temp", ".part", ".partial"}
TEMP_AUDIO_SUFFIXES = {".wav"}
MAX_RECORDED_DELETED_PATHS = 80


class OutputCleanupService:
    """Create a publish manifest and remove heavy per-video render intermediates."""

    def finalize_success_output(
        self,
        output: DouyinOutputResult,
        settings: DouyinReupSettings,
        video_dir: str | Path,
    ) -> DouyinOutputResult:
        if output.status != "success":
            return output
        report = self.cleanup_after_success(output, settings, video_dir)
        updates: dict[str, Any] = {"cleanup_report": report}
        manifest_file = report.get("publish_manifest_file")
        if isinstance(manifest_file, str) and manifest_file:
            updates["publish_manifest_file"] = manifest_file
        return output.model_copy(update=updates)

    def cleanup_after_success(
        self,
        output: DouyinOutputResult,
        settings: DouyinReupSettings,
        video_dir: str | Path,
    ) -> dict[str, Any]:
        root = Path(video_dir).expanduser().resolve()
        warnings: list[str] = []
        errors: list[str] = []
        final_video = Path(output.path).expanduser() if output.path else None
        final_video_resolved = _resolve_path(final_video) if final_video else None
        report: dict[str, Any] = {
            "enabled": not settings.keep_temp,
            "status": "skipped",
            "skipped_reason": None,
            "deleted_size_bytes": 0,
            "deleted_file_count": 0,
            "deleted_paths": [],
            "publish_manifest_file": None,
            "warnings": warnings,
            "errors": errors,
        }

        if not root.exists():
            errors.append(f"Thu muc ket qua khong ton tai: {root}")
            report["status"] = "warning"
            return report

        if not final_video_resolved or not final_video_resolved.exists() or final_video_resolved.suffix.lower() != ".mp4":
            report["skipped_reason"] = "missing_final_mp4"
            warnings.append("Bo qua cleanup vi chua thay file MP4 ket qua hop le.")
            return report

        if _path_size(final_video_resolved)[0] <= 0:
            report["skipped_reason"] = "empty_final_mp4"
            warnings.append("Bo qua cleanup vi file MP4 ket qua dang rong.")
            return report

        qa_status = _qa_status(output)
        manifest_path = self._write_publish_manifest(output, root, qa_status)
        report["publish_manifest_file"] = str(manifest_path)

        if settings.keep_temp:
            report["skipped_reason"] = "keep_temp_enabled"
            return report

        if qa_status == "failed":
            report["skipped_reason"] = "final_qa_failed"
            warnings.append("Bo qua cleanup vi QA cuoi dang bao loi, can giu file debug de kiem tra.")
            return report

        protected = _protected_paths(output, manifest_path)
        candidates = _cleanup_candidates(root, protected)
        deleted_paths: list[str] = []
        deleted_size = 0
        deleted_count = 0

        for path in candidates:
            resolved = _resolve_path(path)
            if resolved is None or not resolved.exists():
                continue
            if not _is_relative_to(resolved, root):
                warnings.append(f"Bo qua ngoai thu muc ket qua: {resolved}")
                continue
            if _is_protected(resolved, protected):
                continue
            size, count = _path_size(resolved)
            try:
                _delete_path(resolved)
            except OSError as exc:
                errors.append(f"Khong the xoa {resolved}: {exc}")
                continue
            deleted_size += size
            deleted_count += count
            if len(deleted_paths) < MAX_RECORDED_DELETED_PATHS:
                deleted_paths.append(str(resolved))

        report.update(
            {
                "status": "completed" if not errors else "warning",
                "deleted_size_bytes": deleted_size,
                "deleted_file_count": deleted_count,
                "deleted_paths": deleted_paths,
            }
        )
        return report

    def _write_publish_manifest(
        self,
        output: DouyinOutputResult,
        video_dir: Path,
        qa_status: str | None,
    ) -> Path:
        manifest_path = video_dir / "publish_manifest.json"
        product_name = _product_name(output.product_detection)
        caption_lines = _caption_lines(output)
        hashtags = _hashtag_suggestions(product_name, caption_lines, output)
        payload = {
            "version": 1,
            "created_at": datetime.now().replace(microsecond=0).isoformat(),
            "ready_for_publish": qa_status != "failed",
            "status": output.status,
            "qa_status": qa_status,
            "output_video_path": output.path,
            "source_video_path": output.source_video,
            "title_suggestion": product_name or Path(output.path).stem,
            "caption_suggestions": caption_lines[:8],
            "hashtags": hashtags,
            "reup_mode": output.reup_mode,
            "silent_strategy": output.silent_strategy,
            "caption_source": output.caption_source,
            "subtitle_source": output.subtitle_source,
            "product_detection": output.product_detection,
            "files": {
                "video": output.path,
                "source_srt": output.source_srt_file,
                "translated_srt": output.translated_srt_file,
                "corrected_srt": output.corrected_srt_file,
                "subtitle_ass": output.subtitle_ass_file,
                "voiceover_script": output.voiceover_script_file,
                "voiceover_subtitle": output.voiceover_subtitle_file,
                "log": output.log_file,
                "qa_report": (output.final_output_qa or {}).get("report_path")
                if isinstance(output.final_output_qa, dict)
                else None,
            },
        }
        ensure_dir(manifest_path.parent)
        write_json(manifest_path, payload)
        return manifest_path


def _cleanup_candidates(root: Path, protected: set[Path]) -> list[Path]:
    candidates: list[Path] = []
    source_copy = root / "source.mp4"
    if source_copy.exists():
        candidates.append(source_copy)

    for path in root.rglob("*"):
        try:
            if _is_protected(path, protected):
                continue
            lower_name = path.name.lower()
            if path.is_dir() and lower_name in TEMP_DIR_NAMES:
                candidates.append(path)
                continue
            if path.is_file():
                suffix = path.suffix.lower()
                if suffix in TEMP_FILE_SUFFIXES or suffix in TEMP_AUDIO_SUFFIXES:
                    candidates.append(path)
        except OSError:
            continue

    return _dedupe_outermost(candidates)


def _dedupe_outermost(paths: list[Path]) -> list[Path]:
    resolved: list[Path] = []
    seen: set[str] = set()
    for path in sorted(paths, key=lambda item: len(str(item))):
        item = _resolve_path(path)
        if item is None:
            continue
        key = str(item).lower()
        if key in seen:
            continue
        if any(_is_relative_to(item, parent) for parent in resolved if parent != item):
            continue
        seen.add(key)
        resolved.append(item)
    return resolved


def _protected_paths(output: DouyinOutputResult, manifest_path: Path) -> set[Path]:
    values = [
        output.path,
        output.source_srt_file,
        output.translated_srt_file,
        output.corrected_srt_file,
        output.subtitle_ass_file,
        output.overlay_file,
        output.bgm_file,
        output.log_file,
        output.silent_plan_file,
        output.voiceover_file,
        output.voiceover_script_file,
        output.voiceover_subtitle_file,
        output.ocr_debug_json_path,
        (output.final_output_qa or {}).get("report_path") if isinstance(output.final_output_qa, dict) else None,
        str(manifest_path),
    ]
    protected: set[Path] = set()
    for value in values:
        if not value:
            continue
        resolved = _resolve_path(Path(str(value)).expanduser())
        if resolved is not None:
            protected.add(resolved)
    return protected


def _is_protected(path: Path, protected: set[Path]) -> bool:
    resolved = _resolve_path(path)
    if resolved is None:
        return False
    return any(resolved == item or _is_relative_to(item, resolved) for item in protected)


def _delete_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _path_size(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    if path.is_file() or path.is_symlink():
        try:
            return path.stat().st_size, 1
        except OSError:
            return 0, 0
    total = 0
    count = 0
    for item in path.rglob("*"):
        try:
            if item.is_file() and not item.is_symlink():
                total += item.stat().st_size
                count += 1
        except OSError:
            continue
    return total, count


def _resolve_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    try:
        return path.expanduser().resolve()
    except OSError:
        return None


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _qa_status(output: DouyinOutputResult) -> str | None:
    if isinstance(output.final_output_qa, dict):
        status = output.final_output_qa.get("status")
        return str(status) if status else None
    return None


def _caption_lines(output: DouyinOutputResult) -> list[str]:
    source = output.corrected_srt_file or output.translated_srt_file or output.voiceover_subtitle_file
    if not source:
        return []
    path = Path(source)
    if not path.exists():
        return []
    try:
        blocks = parse_srt_blocks(str(path))
    except OSError:
        return []
    lines: list[str] = []
    seen: set[str] = set()
    for block in blocks:
        text = re.sub(r"\s+", " ", block.text).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        lines.append(text)
        if len(lines) >= 12:
            break
    return lines


def _product_name(report: dict[str, Any] | None) -> str:
    if not isinstance(report, dict):
        return ""
    candidate = report.get("top_candidate")
    if not isinstance(candidate, dict):
        candidates = report.get("candidates")
        if isinstance(candidates, list) and candidates and isinstance(candidates[0], dict):
            candidate = candidates[0]
    if not isinstance(candidate, dict):
        return ""
    for key in ("display_name", "name", "product_name", "label"):
        value = candidate.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _hashtag_suggestions(product_name: str, caption_lines: list[str], output: DouyinOutputResult) -> list[str]:
    text = " ".join([product_name, Path(output.path).stem if output.path else "", *caption_lines])
    hashtags = re.findall(r"#[\w\-\u0080-\uffff]+", text)
    cleaned: list[str] = []
    for item in hashtags:
        tag = item.strip().rstrip(".,;:!?")
        key = tag.lower()
        if tag and key not in {value.lower() for value in cleaned}:
            cleaned.append(tag)
    for fallback in ("#review", "#sanpham", "#douyin"):
        if len(cleaned) >= 8:
            break
        if fallback.lower() not in {value.lower() for value in cleaned}:
            cleaned.append(fallback)
    return cleaned[:8]
