from app.modules.final_output_qa.audio_quality_checker import AudioQualityChecker
from tests.final_output_qa_helpers import make_video


def test_audio_quality_checker_detects_quiet_audio(tmp_path):
    video = make_video(tmp_path / "quiet.mp4", audio_volume=0.0005)

    result = AudioQualityChecker().analyze_audio(str(video), has_audio=True)

    assert result.has_audio is True
    assert result.mean_volume_db is not None
    assert result.mean_volume_db < -35
    assert any("quiet" in warning for warning in result.warnings)


def test_audio_quality_checker_handles_no_audio(tmp_path):
    video = make_video(tmp_path / "silent.mp4", with_audio=False)

    result = AudioQualityChecker().analyze_audio(str(video), has_audio=False)

    assert result.has_audio is False
