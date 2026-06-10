from app.modules.final_output_qa.final_output_qa_schema import PlatformTarget
from app.modules.final_output_qa.subtitle_visibility_checker import SubtitleVisibilityChecker


def test_subtitle_visibility_warns_when_expected_file_is_missing(tmp_path):
    result = SubtitleVisibilityChecker().check_subtitle_visibility(
        str(tmp_path / "video.mp4"),
        str(tmp_path / "missing.ass"),
        None,
        PlatformTarget.tiktok,
        subtitle_expected=True,
    )

    assert result.safe_zone_ok is True
    assert any("missing" in warning for warning in result.warnings)


def test_subtitle_visibility_detects_bottom_edge_risk(tmp_path):
    ass = tmp_path / "subtitle.ass"
    ass.write_text(
        "[Script Info]\nPlayResY: 1920\n[V4+ Styles]\n"
        "Style: Default,Arial,70,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,20,1\n",
        encoding="utf-8",
    )

    result = SubtitleVisibilityChecker().check_subtitle_visibility(
        str(tmp_path / "video.mp4"), str(ass), None, PlatformTarget.tiktok
    )

    assert result.safe_zone_ok is False
    assert any("bottom edge" in warning for warning in result.warnings)


def test_subtitle_visibility_uses_vertical_margin_for_safe_zone(tmp_path):
    ass = tmp_path / "subtitle.ass"
    ass.write_text(
        "[Script Info]\nPlayResY: 1920\n[V4+ Styles]\n"
        "Style: Default,Arial,70,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,120,1\n",
        encoding="utf-8",
    )

    result = SubtitleVisibilityChecker().check_subtitle_visibility(
        str(tmp_path / "video.mp4"), str(ass), None, PlatformTarget.tiktok
    )

    assert result.safe_zone_ok is True
    assert result.estimated_subtitle_zone["margin_v"] == 120
    assert result.warnings == []
