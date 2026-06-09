from __future__ import annotations

from dataclasses import dataclass

from app.adapters.ffmpeg_adapter import FFmpegError
from app.modules.douyin_reup import douyin_folder_scanner


@dataclass
class FakeMedia:
    path: str
    duration: float = 12.0
    width: int = 1080
    height: int = 1920
    fps: float = 30.0
    has_audio: bool = True
    format_name: str = "mov,mp4,m4a,3gp,3g2,mj2"


def test_douyin_folder_scanner_detects_video_and_sidecar_srt(tmp_path, monkeypatch):
    video = tmp_path / "clip.mp4"
    srt = tmp_path / "clip.srt"
    ignored = tmp_path / "note.txt"
    video.write_bytes(b"fake video")
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\n你好\n", encoding="utf-8")
    ignored.write_text("ignore", encoding="utf-8")

    monkeypatch.setattr(
        douyin_folder_scanner,
        "probe_video",
        lambda path: FakeMedia(path=path),
    )
    monkeypatch.setattr(douyin_folder_scanner, "has_embedded_text_subtitle", lambda path: True)

    scanner = douyin_folder_scanner.DouyinFolderScanner()
    media = scanner.scan_folder(str(tmp_path))

    assert scanner.total_files == 3
    assert scanner.invalid_files == 2
    assert len(media) == 1
    assert media[0].sidecar_srt_path == str(srt.resolve())
    assert media[0].embedded_subtitle_found is True


def test_douyin_folder_scanner_logs_invalid_probe(tmp_path, monkeypatch):
    video = tmp_path / "broken.mp4"
    video.write_bytes(b"broken")

    def fail_probe(path: str):
        raise FFmpegError("ffprobe failed")

    monkeypatch.setattr(douyin_folder_scanner, "probe_video", fail_probe)

    scanner = douyin_folder_scanner.DouyinFolderScanner()
    media = scanner.scan_folder(str(tmp_path))

    assert media == []
    assert scanner.invalid_files == 1
    assert "ffprobe failed" in scanner.errors[0]
