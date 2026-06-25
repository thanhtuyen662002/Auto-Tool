from __future__ import annotations

import json
from pathlib import Path

from app.modules.douyin_reup.douyin_schema import DouyinOutputResult, DouyinReupSettings
from app.modules.douyin_reup.output_cleanup_service import OutputCleanupService


def _successful_output(video_dir: Path) -> DouyinOutputResult:
    final_video = video_dir / "douyin_001.mp4"
    translated_srt = video_dir / "translated_vi.srt"
    log_file = video_dir / "video_001_log.json"
    qa_report = video_dir / "video_001_final_qa.json"
    final_video.write_bytes(b"final mp4")
    translated_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nDay la caption.\n", encoding="utf-8")
    log_file.write_text("{}", encoding="utf-8")
    qa_report.write_text("{}", encoding="utf-8")
    return DouyinOutputResult(
        index=1,
        path=str(final_video),
        status="success",
        source_video=str(video_dir.parent / "source" / "clip.mp4"),
        translated_srt_file=str(translated_srt),
        log_file=str(log_file),
        final_output_qa={"status": "passed", "score": 0.95, "report_path": str(qa_report), "issues": []},
        product_detection={
            "top_candidate": {"display_name": "Ke bep da nang", "confidence": 0.86},
            "average_confidence": 0.86,
        },
        warnings=[],
        errors=[],
    )


def _add_intermediates(video_dir: Path) -> None:
    (video_dir / "source.mp4").write_bytes(b"copied source")
    (video_dir / "frames").mkdir()
    (video_dir / "frames" / "frame_001.jpg").write_bytes(b"frame")
    (video_dir / "ocr" / "ocr_frames" / "_ocr_crop").mkdir(parents=True)
    (video_dir / "ocr" / "ocr_frames" / "frame_001.jpg").write_bytes(b"ocr frame")
    (video_dir / "ocr" / "ocr_frames" / "_ocr_crop" / "crop_001.jpg").write_bytes(b"crop")
    (video_dir / "mixed_audio.wav").write_bytes(b"temp audio")


def test_cleanup_removes_heavy_intermediates_and_keeps_publish_files(tmp_path):
    video_dir = tmp_path / "output" / "video_001"
    video_dir.mkdir(parents=True)
    output = _successful_output(video_dir)
    _add_intermediates(video_dir)

    result = OutputCleanupService().finalize_success_output(output, DouyinReupSettings(keep_temp=False), video_dir)

    assert result.publish_manifest_file
    assert result.cleanup_report
    assert result.cleanup_report["status"] == "completed"
    assert result.cleanup_report["deleted_file_count"] >= 4
    assert result.cleanup_report["deleted_size_bytes"] > 0
    assert Path(output.path).exists()
    assert Path(output.translated_srt_file or "").exists()
    assert Path(output.log_file or "").exists()
    assert not (video_dir / "source.mp4").exists()
    assert not (video_dir / "frames").exists()
    assert not (video_dir / "ocr" / "ocr_frames").exists()
    assert not (video_dir / "mixed_audio.wav").exists()

    manifest = json.loads(Path(result.publish_manifest_file).read_text(encoding="utf-8"))
    assert manifest["ready_for_publish"] is True
    assert manifest["output_video_path"] == output.path
    assert manifest["title_suggestion"] == "Ke bep da nang"
    assert "Day la caption." in manifest["caption_suggestions"]


def test_cleanup_keep_temp_writes_manifest_without_deleting_intermediates(tmp_path):
    video_dir = tmp_path / "output" / "video_001"
    video_dir.mkdir(parents=True)
    output = _successful_output(video_dir)
    _add_intermediates(video_dir)

    result = OutputCleanupService().finalize_success_output(output, DouyinReupSettings(keep_temp=True), video_dir)

    assert result.publish_manifest_file
    assert result.cleanup_report
    assert result.cleanup_report["status"] == "skipped"
    assert result.cleanup_report["skipped_reason"] == "keep_temp_enabled"
    assert (video_dir / "source.mp4").exists()
    assert (video_dir / "frames" / "frame_001.jpg").exists()
    assert (video_dir / "mixed_audio.wav").exists()


def test_cleanup_skips_deletion_when_final_qa_failed(tmp_path):
    video_dir = tmp_path / "output" / "video_001"
    video_dir.mkdir(parents=True)
    output = _successful_output(video_dir).model_copy(
        update={"final_output_qa": {"status": "failed", "score": 0.2, "report_path": None, "issues": []}}
    )
    _add_intermediates(video_dir)

    result = OutputCleanupService().finalize_success_output(output, DouyinReupSettings(keep_temp=False), video_dir)

    assert result.publish_manifest_file
    assert result.cleanup_report
    assert result.cleanup_report["status"] == "skipped"
    assert result.cleanup_report["skipped_reason"] == "final_qa_failed"
    assert (video_dir / "source.mp4").exists()
    assert (video_dir / "frames" / "frame_001.jpg").exists()
