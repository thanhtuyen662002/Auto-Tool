"""
Auto Tool Smoke Test

Chay kiem tra end-to-end nhanh de xac nhan moi truong va pipeline hoat dong.

Su dung:
    py -m app.tools.smoke_test --config ../examples/qa_projects/projector_config.json
    py -m app.tools.smoke_test --config ../examples/qa_projects/projector_config.json --no-mock
"""
from __future__ import annotations

import argparse
import io
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# Force UTF-8 output on Windows to avoid UnicodeEncodeError with Vietnamese text
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(msg: str = "") -> dict[str, Any]:
    return {"status": "ok", "message": msg}


def _skip(msg: str = "") -> dict[str, Any]:
    return {"status": "skip", "message": msg}


def _fail(msg: str) -> dict[str, Any]:
    return {"status": "fail", "message": msg}


def _print_step(index: int, name: str, result: dict[str, Any]) -> None:
    icon = {"ok": "[OK]  ", "skip": "[SKIP]", "fail": "[FAIL]"}.get(result["status"], "[?]   ")
    msg = result.get("message", "")
    suffix = f" -- {msg}" if msg else ""
    print(f"  {icon} [{index:02d}] {name}{suffix}")


# ---------------------------------------------------------------------------
# Individual steps
# ---------------------------------------------------------------------------

def step_load_config(config_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if not config_path.exists():
        return {}, _fail(f"File config không tồn tại: {config_path}")
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return data, _ok(f"Đã tải config từ {config_path.name}")
    except json.JSONDecodeError as exc:
        return {}, _fail(f"Config JSON không hợp lệ: {exc}")
    except Exception as exc:
        return {}, _fail(f"Không thể đọc config: {exc}")


def step_check_environment() -> dict[str, Any]:
    issues: list[str] = []

    # Python version
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 11):
        issues.append(f"Python >= 3.11 required, found {major}.{minor}")

    # FFmpeg
    if not shutil.which("ffmpeg"):
        issues.append("FFmpeg không tìm thấy trong PATH. Hãy cài FFmpeg trước khi render video.")

    # ffprobe
    if not shutil.which("ffprobe"):
        issues.append("ffprobe không tìm thấy trong PATH. Đây là thành phần của FFmpeg.")

    if issues:
        return _fail("; ".join(issues))
    return _ok(f"Python {major}.{minor}, FFmpeg OK, ffprobe OK")


def step_scan_video(config: dict[str, Any], mock: bool) -> tuple[list[Any], dict[str, Any]]:
    if mock:
        return [{"path": "mock_video.mp4", "duration": 30.0}], _ok("Mock: 1 video giả")

    source_folder = config.get("source_folder", "")
    if not source_folder:
        return [], _fail("source_folder không được khai báo trong config")

    folder = Path(source_folder)
    if not folder.exists():
        return [], _fail(
            f"Thư mục nguồn không tồn tại: {folder}\n"
            "  → Hãy tạo thư mục và bỏ video vào đó trước khi chạy smoke test thật."
        )

    try:
        from app.modules.media_scanner.scanner import MediaScanner
        media = MediaScanner().scan_folder(source_folder)
        if not media:
            return [], _fail(
                f"Không tìm thấy video hợp lệ trong {folder}\n"
                "  → Bỏ file .mp4/.mov vào thư mục và thử lại."
            )
        return media, _ok(f"{len(media)} video hợp lệ")
    except Exception as exc:
        return [], _fail(f"Scan thất bại: {_friendly(exc)}")


def step_create_segments(media: list[Any], mock: bool) -> tuple[list[Any], dict[str, Any]]:
    if mock:
        from app.schemas.media_schema import MediaFile
        from app.modules.segmenter.segmenter import Segmenter
        fake_media = [MediaFile(
            path="mock.mp4",
            duration=30.0,
            width=1080,
            height=1920,
            fps=30.0,
            has_audio=True,
            format_name="mp4",
        )]
        segments = Segmenter().create_segments(fake_media, cut_intensity=50)
        return segments, _ok(f"Mock: {len(segments)} segments")

    try:
        from app.modules.segmenter.segmenter import Segmenter
        segments = Segmenter().create_segments(media, cut_intensity=50)
        if not segments:
            return [], _fail("Không tạo được segment nào từ video nguồn.")
        return segments, _ok(f"{len(segments)} segments")
    except Exception as exc:
        return [], _fail(f"Segment thất bại: {_friendly(exc)}")


def step_score_segments(segments: list[Any]) -> tuple[list[Any], dict[str, Any]]:
    try:
        from app.modules.segment_scoring.segment_scorer import SegmentScorer, build_scoring_report
        scored = SegmentScorer().score_segments(segments)
        report = build_scoring_report(scored)
        return scored, _ok(
            f"usable={report['usable_segments']}, rejected={report['rejected_segments']}, "
            f"avg_score={report['average_score']}"
        )
    except Exception as exc:
        return [], _fail(f"Scoring thất bại: {_friendly(exc)}")


def step_build_timeline(segments: list[Any], config: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    try:
        from app.modules.timeline_templates.product_timeline_builder import ProductTimelineBuilder
        template_id = (config.get("timeline") or {}).get("template_id", "ugc_reviewer_natural")
        duration = (config.get("render") or {}).get("duration", 12)
        speed_variation = (config.get("effects") or {}).get("speed_variation", 30)
        usable = [s for s in segments if s.score_detail is not None and not s.score_detail.is_rejected] or segments
        timelines = ProductTimelineBuilder().build_timelines(
            segments=usable,
            output_count=1,
            target_duration=duration,
            template_id=template_id,
            speed_variation=speed_variation,
        )
        if not timelines:
            return None, _fail("Không tạo được timeline")
        return timelines[0], _ok(f"template={template_id}, duration={duration}s")
    except Exception as exc:
        return None, _fail(f"Timeline that bai: {_friendly(exc)}")


def step_generate_script(config: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    try:
        from app.schemas.project_schema import ProjectConfig
        project_config = ProjectConfig.model_validate(config)
        # Nếu không có Gemini API key, dùng script mẫu thay vì gọi API
        if not project_config.ai.gemini_api_keys:
            from app.modules.script_writer.script_writer import ProductVideoScript
            script = ProductVideoScript(
                hook="[Mock] Sản phẩm tuyệt vời!",
                voiceover=[{"time_hint": "0-4s", "text": "Đây là smoke test kịch bản giả."}],
                subtitles=[{"start_hint": 0, "end_hint": 4, "text": "Smoke test kịch bản giả."}],
                cta="Xem ngay",
                caption="Caption smoke test",
                hashtags=["#smoketest"],
            )
            return script, _ok("Mock: không có Gemini API key → dùng script mẫu")

        from app.modules.script_writer.script_writer import ScriptWriter
        writer = ScriptWriter()
        script = writer.generate_script(project_config, output_index=1)
        return script, _ok(f"hook={script.hook[:40]}...")
    except Exception as exc:
        return None, _fail(f"Script thất bại: {_friendly(exc)}")


def step_generate_tts(script: Any, tmp_dir: Path, mock: bool) -> tuple[str | None, dict[str, Any]]:
    if mock or script is None:
        fake_path = str(tmp_dir / "smoke_voice.mp3")
        Path(fake_path).write_bytes(b"MOCK_MP3")
        return fake_path, _ok("Mock: file voice giả")

    try:
        from app.modules.tts.providers.edge_tts_provider import EdgeTTSProvider
        from app.modules.tts.tts_schema import TTSSettings
        output_path = str(tmp_dir / "smoke_voice.mp3")
        result = EdgeTTSProvider().generate(
            text=script.hook or "Đây là smoke test.",
            output_path=output_path,
            settings=TTSSettings(),
        )
        return result.output_path, _ok(f"duration={result.duration:.1f}s via {result.provider}")
    except Exception as exc:
        fake_path = str(tmp_dir / "smoke_voice.mp3")
        Path(fake_path).write_bytes(b"MOCK_MP3")
        return fake_path, _ok(
            f"Edge TTS lỗi ({_friendly(exc)}), dùng file giả để tiếp tục"
        )


def step_generate_subtitle(script: Any, tmp_dir: Path) -> dict[str, Any]:
    if script is None:
        return _skip("Không có script")
    try:
        from app.modules.subtitle_generator.subtitle_generator import SubtitleGenerator
        sub_path = str(tmp_dir / "smoke_sub.srt")
        SubtitleGenerator().generate_srt(
            script=script,
            target_video_duration=12.0,
            output_path=sub_path,
        )
        size = Path(sub_path).stat().st_size
        return _ok(f"SRT {size} bytes")
    except Exception as exc:
        return _fail(f"Subtitle that bai: {_friendly(exc)}")


def step_render_preview(timeline: Any, config: dict[str, Any], voice_path: str | None, tmp_dir: Path, mock: bool) -> tuple[str | None, dict[str, Any]]:
    if mock or timeline is None or voice_path is None:
        fake_path = str(tmp_dir / "smoke_preview.mp4")
        Path(fake_path).write_bytes(b"MOCK_MP4")
        return fake_path, _ok("Mock: file preview giả (không có video thật)")

    try:
        from app.schemas.project_schema import ProjectConfig
        from app.modules.renderer.renderer import Renderer
        project_config = ProjectConfig.model_validate(config)
        out = str(tmp_dir / "smoke_preview.mp4")
        Renderer().render_timeline(timeline, project_config, str(tmp_dir), base_name="smoke_preview")
        return out, _ok("Render preview hoàn thành")
    except Exception as exc:
        return None, _fail(f"Render thất bại: {_friendly(exc)}")


def step_qa_check(preview_path: str | None, mock: bool) -> dict[str, Any]:
    if mock or not preview_path:
        return _ok("Mock: QA bỏ qua (không có video thật)")
    try:
        from app.modules.qa_checker.qa_checker import check_output_video
        result = check_output_video(preview_path, 12.0)
        if result.get("errors"):
            return _fail(f"QA errors: {result['errors']}")
        warnings = result.get("warnings", [])
        return _ok(f"QA passed" + (f", {len(warnings)} warnings" if warnings else ""))
    except Exception as exc:
        return _fail(f"QA thất bại: {_friendly(exc)}")


# ---------------------------------------------------------------------------
# Friendly error messages
# ---------------------------------------------------------------------------

def _friendly(exc: Exception) -> str:
    msg = str(exc)
    if "ffmpeg" in msg.lower() or "ffprobe" in msg.lower():
        return "Không tìm thấy FFmpeg. Hãy cài FFmpeg và thêm vào PATH."
    if "network" in msg.lower() or "connection" in msg.lower() or "timeout" in msg.lower():
        return f"Lỗi mạng: {msg[:120]}"
    if "json" in msg.lower() or "invalid" in msg.lower():
        return f"Dữ liệu không hợp lệ: {msg[:120]}"
    if "permission" in msg.lower():
        return f"Lỗi quyền truy cập: {msg[:120]}"
    # Truncate long messages
    return msg[:200]


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_smoke_test(config_path: Path, mock: bool) -> dict[str, Any]:
    import tempfile

    tmp_dir = Path(tempfile.mkdtemp(prefix="autotool_smoke_"))
    steps: dict[str, Any] = {}
    overall = "success"

    print(f"\n[*] Auto Tool Smoke Test")
    print(f"   Config : {config_path}")
    print(f"   Mode   : {'mock (dung du lieu gia)' if mock else 'real (can video that)'}")
    print(f"   Tmpdir : {tmp_dir}")
    print()

    # Step 1: Load config
    config, r1 = step_load_config(config_path)
    steps["load_config"] = r1["status"]
    _print_step(1, "Load config", r1)
    if r1["status"] == "fail":
        overall = "fail"
        return _build_result(overall, steps, None)

    # Step 2: Check environment
    r2 = step_check_environment()
    steps["check_env"] = r2["status"]
    _print_step(2, "Check environment", r2)
    if r2["status"] == "fail":
        overall = "fail"

    # Step 3: Scan video
    media, r3 = step_scan_video(config, mock)
    steps["scan"] = r3["status"]
    _print_step(3, "Scan video", r3)
    if r3["status"] == "fail":
        overall = "fail"

    # Step 4: Create segments
    segments, r4 = step_create_segments(media, mock)
    steps["segment"] = r4["status"]
    _print_step(4, "Create segments", r4)
    if r4["status"] == "fail":
        overall = "fail"

    # Step 5: Score segments
    scored_segments, r5 = step_score_segments(segments) if segments else ([], _skip("Không có segments"))
    steps["segment_scoring"] = r5["status"]
    _print_step(5, "Score segments", r5)

    # Step 6: Build timeline
    timeline, r6 = step_build_timeline(scored_segments or segments, config) if (scored_segments or segments) else (None, _skip("Không có segments"))
    steps["timeline"] = r6["status"]
    _print_step(6, "Build timeline", r6)
    if r6["status"] == "fail":
        overall = "fail"

    # Step 7: Generate script
    script, r7 = step_generate_script(config)
    steps["script"] = r7["status"]
    _print_step(7, "Generate script", r7)
    if r7["status"] == "fail":
        overall = "fail"

    # Step 8: Generate TTS
    voice_path, r8 = step_generate_tts(script, tmp_dir, mock)
    steps["tts"] = r8["status"]
    _print_step(8, "Generate TTS", r8)

    # Step 9: Generate subtitle
    r9 = step_generate_subtitle(script, tmp_dir)
    steps["subtitle"] = r9["status"]
    _print_step(9, "Generate subtitle", r9)
    if r9["status"] == "fail":
        overall = "fail"

    # Step 10: Render preview
    preview_path, r10 = step_render_preview(timeline, config, voice_path, tmp_dir, mock)
    steps["render_preview"] = r10["status"]
    _print_step(10, "Render preview", r10)
    if r10["status"] == "fail":
        overall = "fail"

    # Step 11: QA check
    r11 = step_qa_check(preview_path, mock)
    steps["qa"] = r11["status"]
    _print_step(11, "QA check", r11)
    if r11["status"] == "fail":
        overall = "fail"

    return _build_result(overall, steps, preview_path)


def _build_result(status: str, steps: dict[str, Any], preview_path: str | None) -> dict[str, Any]:
    return {
        "status": status,
        "steps": steps,
        "preview_path": preview_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auto Tool Smoke Test — kiểm tra end-to-end nhanh"
    )
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Đường dẫn tới file config JSON (ví dụ: ../examples/qa_projects/projector_config.json)",
    )
    parser.add_argument(
        "--no-mock",
        action="store_true",
        default=False,
        help="Chạy với video thật (mặc định dùng mock nếu không có video)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Chỉ in JSON output (không in progress)",
    )
    args = parser.parse_args()

    # Add backend to path if needed
    backend_dir = Path(__file__).resolve().parents[2]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    mock_mode = not args.no_mock

    if args.json:
        # Silent mode
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = run_smoke_test(args.config, mock_mode)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        result = run_smoke_test(args.config, mock_mode)
        print()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    # Exit code
    if result["status"] == "fail":
        sys.exit(1)


if __name__ == "__main__":
    main()
