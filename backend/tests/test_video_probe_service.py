from app.modules.final_output_qa.video_probe_service import VideoProbeService
from tests.final_output_qa_helpers import make_video


def test_video_probe_handles_missing_file(tmp_path):
    probe = VideoProbeService().probe_video(str(tmp_path / "missing.mp4"))

    assert probe.exists is False
    assert probe.readable is False


def test_video_probe_reads_vertical_video_metadata(tmp_path):
    video = make_video(tmp_path / "vertical.mp4", width=720, height=1280)

    probe = VideoProbeService().probe_video(str(video))

    assert probe.readable is True
    assert probe.width == 720
    assert probe.height == 1280
    assert probe.video_codec == "h264"
    assert probe.audio_codec == "aac"
    assert probe.has_audio is True
    assert probe.file_size_mb and probe.file_size_mb > 0
