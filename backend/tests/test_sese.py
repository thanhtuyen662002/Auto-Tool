"""
Unit tests for Smart Ending Synchronization Engine (SESE).

Tests cover:
- Case 3: delta <= 0.5s → no adjustment
- Case 2: video > voice → no adjustment (negative delta)
- Case 1a: voice > video, extend_last succeeds
- Case 1b: voice > video, extend_last unavailable, extend_nearby succeeds
- Case 1c: voice > video, neither extend available → freeze / freeze_zoom clip appended
- Guard: delta > max_allowed → trim strategy
- Guard: delta > max_allowed → fail strategy raises ValueError
- sese_enabled=False in config → caller-level guard test (SESE engine always runs when called)
- Metadata recording on adjusted_timeline
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.sese.sese_engine import SESEEngine
from app.modules.timeline_builder.timeline_builder import ClipType, Timeline, TimelineClip
from app.schemas.project_schema import (
    AISettings,
    CacheSettings,
    CropSafetySettings,
    EffectSettings,
    MusicSettings,
    ProductInfo,
    ProjectConfig,
    RenderSettings,
    TimelineSettings,
    TTSSettings,
    VisualStyleSettings,
)
from app.modules.visual_style.style_schema import VisualStyleSettings as StyleSchemaSettings


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _make_clip(
    source_path: str = "video.mp4",
    start: float = 0.0,
    end: float = 5.0,
    duration: float = 5.0,
    speed: float = 1.0,
    clip_type: ClipType = ClipType.NORMAL,
) -> TimelineClip:
    return TimelineClip(
        source_path=source_path,
        start=start,
        end=end,
        duration=duration,
        speed=speed,
        clip_type=clip_type,
    )


def _make_timeline(clips: list[TimelineClip], target_duration: float = 10.0) -> Timeline:
    return Timeline(
        output_index=1,
        target_duration=target_duration,
        clips=clips,
    )


def _make_config(
    sese_enabled: bool = True,
    max_auto_extension_seconds: float = 8.0,
    max_auto_extension_ratio: float = 0.4,
    sese_failure_strategy: str = "trim",
) -> ProjectConfig:
    return ProjectConfig(
        project_name="test",
        source_folder=".",
        output_folder=".",
        product=ProductInfo(
            name="Test",
            description="Test product",
            features=["Feature 1"],
            cta="Buy now",
        ),
        render=RenderSettings(
            output_count=1,
            duration=10.0,
            aspect_ratio="9:16",
            resolution="1080x1920",
            fps=30,
            sese_enabled=sese_enabled,
            max_auto_extension_seconds=max_auto_extension_seconds,
            max_auto_extension_ratio=max_auto_extension_ratio,
            sese_failure_strategy=sese_failure_strategy,
        ),
        effects=EffectSettings(
            cut_intensity=70,
            speed_variation=30,
            grain=0,
            zoom_motion=25,
            overlay_height=33,
            subtitle_size=22,
        ),
        ai=AISettings(text_model="gpt-4", tone="friendly", language="vi"),
        music=MusicSettings(enabled=False, volume=0.1, fade_in=0.5, fade_out=0.5, duck_under_voice=False),
        timeline=TimelineSettings(template_id="ugc_reviewer_natural"),
        tts=TTSSettings(
            provider="edge_tts",
            fallback_provider="piper",
            voice="vi-VN-HoaiMyNeural",
            language="vi",
            rate="+0%",
            pitch="+0Hz",
            volume="+0%",
            output_format="mp3",
        ),
        visual_style=StyleSchemaSettings(preset_id="clean_review_light"),
        crop_safety=CropSafetySettings(
            enabled=True,
            mode="auto_safe",
            allow_blur_background=True,
            reduce_zoom_on_risk=True,
            reduce_overlay_on_risk=True,
        ),
        cache=CacheSettings(
            enabled=True,
            cache_media_metadata=True,
            cache_segment_scoring=True,
            cache_crop_safety=True,
            cache_tts=True,
            cache_overlay_assets=True,
            clear_cache_before_render=False,
        ),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Case 3: No adjustment needed (delta <= 0.5s)
# ──────────────────────────────────────────────────────────────────────────────

def test_no_adjustment_when_delta_is_small():
    """delta = 0.3s → SESE should return unchanged timeline."""
    clips = [_make_clip(start=0.0, end=10.0, duration=10.0)]
    timeline = _make_timeline(clips, target_duration=10.0)
    config = _make_config()

    result = SESEEngine.synchronize(timeline, voice_duration=10.3, config=config)

    # Timeline should have same number of clips (unchanged)
    assert len(result.clips) == 1
    assert result.clips[0].duration == 10.0
    # When delta <= 0.5, SESE returns early and sese_metadata is NOT set
    sese_meta = getattr(result, "sese_metadata", {})
    # Either no metadata at all, or applied is False/missing
    assert not sese_meta.get("applied", False)


def test_no_adjustment_when_voice_shorter():
    """voice < video → no adjustment (negative delta)."""
    clips = [_make_clip(start=0.0, end=10.0, duration=10.0)]
    timeline = _make_timeline(clips, target_duration=10.0)
    config = _make_config()

    result = SESEEngine.synchronize(timeline, voice_duration=8.0, config=config)

    assert len(result.clips) == 1
    assert result.clips[0].duration == 10.0


# ──────────────────────────────────────────────────────────────────────────────
# Case 1a: extend_last succeeds
# ──────────────────────────────────────────────────────────────────────────────

def test_extend_last_clip_when_source_has_room():
    """
    voice_duration = 13.0, timeline_duration = 10.0 → delta = 3.0s
    Source file duration = 20.0s, last clip end = 10.0 → 10s of room available.
    Should extend last clip by 3.0s.
    """
    clips = [
        _make_clip(start=0.0, end=5.0, duration=5.0),
        _make_clip(start=5.0, end=10.0, duration=5.0),
    ]
    timeline = _make_timeline(clips, target_duration=10.0)
    config = _make_config()

    with patch("app.modules.sese.sese_engine.probe_media_duration", return_value=20.0):
        result = SESEEngine.synchronize(timeline, voice_duration=13.0, config=config)

    assert len(result.clips) == 2
    last = result.clips[-1]
    assert abs(last.duration - 8.0) < 0.01   # 5.0 + 3.0 = 8.0
    meta = getattr(result, "sese_metadata", {})
    assert meta["strategy"] == "extend_last"
    assert meta["applied"] is True
    assert abs(meta["added_duration"] - 3.0) < 0.01


# ──────────────────────────────────────────────────────────────────────────────
# Case 1b: extend_last fails, extend_nearby succeeds
# ──────────────────────────────────────────────────────────────────────────────

def test_extend_nearby_when_last_clip_has_no_room():
    """
    Last clip has no room (source_dur = last clip end), second-to-last has room.
    """
    clips = [
        _make_clip(source_path="a.mp4", start=0.0, end=5.0, duration=5.0),
        _make_clip(source_path="b.mp4", start=5.0, end=10.0, duration=5.0),
    ]
    timeline = _make_timeline(clips, target_duration=10.0)
    config = _make_config()

    # probe_media_duration:
    # - last clip (b.mp4) has source_dur = 10.0 (exactly at end, no room)
    # - second-to-last (a.mp4) has source_dur = 20.0 (plenty of room)
    def mock_probe(path: str) -> float:
        return 10.0 if "b.mp4" in path else 20.0

    with patch("app.modules.sese.sese_engine.probe_media_duration", side_effect=mock_probe):
        result = SESEEngine.synchronize(timeline, voice_duration=12.5, config=config)

    meta = getattr(result, "sese_metadata", {})
    assert meta["strategy"] == "extend_nearby"
    assert meta["applied"] is True


# ──────────────────────────────────────────────────────────────────────────────
# Case 1c: No extension available → freeze clip appended
# ──────────────────────────────────────────────────────────────────────────────

def test_freeze_clip_appended_when_no_extension_available():
    """
    Neither last nor nearby clip can be extended → freeze clip is appended.
    """
    clips = [_make_clip(start=0.0, end=10.0, duration=10.0)]
    timeline = _make_timeline(clips, target_duration=10.0)
    config = _make_config()

    # probe always returns same as clip end → no room
    with patch("app.modules.sese.sese_engine.probe_media_duration", return_value=10.0):
        result = SESEEngine.synchronize(timeline, voice_duration=13.5, config=config)

    assert len(result.clips) == 2
    freeze_clip = result.clips[-1]
    assert freeze_clip.clip_type in (ClipType.FREEZE, ClipType.FREEZE_ZOOM)
    assert abs(freeze_clip.duration - 3.5) < 0.01
    meta = getattr(result, "sese_metadata", {})
    assert meta["applied"] is True
    assert meta["strategy"] in ("freeze", "freeze_zoom")


def test_freeze_clip_type_is_freeze_when_enable_end_zoom_false():
    """When enable_end_zoom = False (config attr), clip_type should be FREEZE."""
    clips = [_make_clip(start=0.0, end=10.0, duration=10.0)]
    timeline = _make_timeline(clips, target_duration=10.0)
    config = _make_config()
    # Patch enable_end_zoom to False
    config.render.__dict__["enable_end_zoom"] = False  # type: ignore[attr-defined]

    with patch("app.modules.sese.sese_engine.probe_media_duration", return_value=10.0):
        result = SESEEngine.synchronize(timeline, voice_duration=12.0, config=config)

    freeze_clip = result.clips[-1]
    assert freeze_clip.clip_type == ClipType.FREEZE


# ──────────────────────────────────────────────────────────────────────────────
# Guard: delta > max_allowed → trim
# ──────────────────────────────────────────────────────────────────────────────

def test_guard_trim_strategy_caps_extension():
    """
    voice_duration = 25.0, timeline_duration = 10.0 → delta = 15.0
    max_auto_extension_seconds = 8.0, max_auto_extension_ratio = 0.4 → max = min(8.0, 4.0) = 4.0
    Should apply 4.0s and emit warning, not fail.
    """
    clips = [_make_clip(start=0.0, end=10.0, duration=10.0)]
    timeline = _make_timeline(clips, target_duration=10.0)
    config = _make_config(
        max_auto_extension_seconds=8.0,
        max_auto_extension_ratio=0.4,
        sese_failure_strategy="trim",
    )

    with patch("app.modules.sese.sese_engine.probe_media_duration", return_value=50.0):
        result = SESEEngine.synchronize(timeline, voice_duration=25.0, config=config)

    meta = getattr(result, "sese_metadata", {})
    assert meta["applied"] is True
    assert abs(meta["added_duration"] - 4.0) < 0.01   # max_allowed = min(8.0, 10.0*0.4) = 4.0
    assert "voice_cut_detected" in meta["warnings"]


# ──────────────────────────────────────────────────────────────────────────────
# Guard: delta > max_allowed → fail strategy
# ──────────────────────────────────────────────────────────────────────────────

def test_guard_fail_strategy_raises_value_error():
    """
    When sese_failure_strategy = 'fail' and delta exceeds max, raise ValueError.
    """
    clips = [_make_clip(start=0.0, end=10.0, duration=10.0)]
    timeline = _make_timeline(clips, target_duration=10.0)
    config = _make_config(
        max_auto_extension_seconds=5.0,
        max_auto_extension_ratio=0.3,
        sese_failure_strategy="fail",
    )

    with patch("app.modules.sese.sese_engine.probe_media_duration", return_value=50.0):
        with pytest.raises(ValueError, match="SESE failed"):
            SESEEngine.synchronize(timeline, voice_duration=25.0, config=config)


# ──────────────────────────────────────────────────────────────────────────────
# Metadata: final_duration is correctly set
# ──────────────────────────────────────────────────────────────────────────────

def test_metadata_final_duration_set_correctly():
    clips = [_make_clip(start=0.0, end=10.0, duration=10.0)]
    timeline = _make_timeline(clips, target_duration=10.0)
    config = _make_config()

    with patch("app.modules.sese.sese_engine.probe_media_duration", return_value=50.0):
        result = SESEEngine.synchronize(timeline, voice_duration=13.0, config=config)

    meta = getattr(result, "sese_metadata", {})
    assert abs(meta["final_duration"] - 13.0) < 0.01
    assert abs(result.target_duration - 13.0) < 0.01


# ──────────────────────────────────────────────────────────────────────────────
# Original timeline is not mutated
# ──────────────────────────────────────────────────────────────────────────────

def test_original_timeline_not_mutated():
    """SESE must return a copy, not mutate the original timeline."""
    clips = [_make_clip(start=0.0, end=10.0, duration=10.0)]
    timeline = _make_timeline(clips, target_duration=10.0)
    original_clip_duration = timeline.clips[0].duration
    config = _make_config()

    with patch("app.modules.sese.sese_engine.probe_media_duration", return_value=50.0):
        result = SESEEngine.synchronize(timeline, voice_duration=13.0, config=config)

    # Original timeline unchanged
    assert timeline.clips[0].duration == original_clip_duration
    # Result is different from original
    assert result is not timeline


# ──────────────────────────────────────────────────────────────────────────────
# Empty clips guard
# ──────────────────────────────────────────────────────────────────────────────

def test_empty_timeline_returns_early():
    """If timeline has no clips, SESE returns it unchanged without crashing."""
    # We can't make a real empty Timeline (min_length=1) so we test via a mock
    mock_timeline = MagicMock(spec=Timeline)
    mock_timeline.clips = []
    mock_timeline.model_copy.return_value = mock_timeline

    config = _make_config()

    result = SESEEngine.synchronize(mock_timeline, voice_duration=15.0, config=config)
    assert result is mock_timeline


# ──────────────────────────────────────────────────────────────────────────────
# trimmed_voice metadata field
# ──────────────────────────────────────────────────────────────────────────────

def test_trim_strategy_sets_trimmed_voice_true():
    """
    When delta > max_allowed and strategy is 'trim', metadata.trimmed_voice must be True.
    """
    clips = [_make_clip(start=0.0, end=10.0, duration=10.0)]
    timeline = _make_timeline(clips, target_duration=10.0)
    config = _make_config(
        max_auto_extension_seconds=4.0,
        max_auto_extension_ratio=0.3,
        sese_failure_strategy="trim",
    )

    with patch("app.modules.sese.sese_engine.probe_media_duration", return_value=50.0):
        result = SESEEngine.synchronize(timeline, voice_duration=25.0, config=config)

    meta = getattr(result, "sese_metadata", {})
    assert meta["trimmed_voice"] is True
    assert "voice_cut_detected" in meta["warnings"]


def test_normal_extension_does_not_set_trimmed_voice():
    """
    When delta <= max_allowed, trimmed_voice must remain False.
    """
    clips = [_make_clip(start=0.0, end=10.0, duration=10.0)]
    timeline = _make_timeline(clips, target_duration=10.0)
    config = _make_config()  # max=8s, ratio=0.4 → max_allowed=min(8,4)=4s; delta=3s → OK

    with patch("app.modules.sese.sese_engine.probe_media_duration", return_value=50.0):
        result = SESEEngine.synchronize(timeline, voice_duration=13.0, config=config)

    meta = getattr(result, "sese_metadata", {})
    assert meta.get("trimmed_voice") is False


# ──────────────────────────────────────────────────────────────────────────────
# sese_mode field in config accepted without validation error
# ──────────────────────────────────────────────────────────────────────────────

def test_sese_mode_accepted_in_config():
    """RenderSettings must accept sese_mode='auto' without raising validation error."""
    from app.schemas.project_schema import RenderSettings

    render = RenderSettings(
        output_count=1,
        duration=12,
        aspect_ratio="9:16",
        resolution="1080x1920",
        fps=30,
        sese_enabled=True,
        sese_mode="auto",
        max_auto_extension_seconds=8.0,
        max_auto_extension_ratio=0.4,
        sese_failure_strategy="trim",
    )
    assert render.sese_mode == "auto"


# ──────────────────────────────────────────────────────────────────────────────
# Preview config bypass
# ──────────────────────────────────────────────────────────────────────────────

def test_preview_config_forces_sese_disabled():
    """_preview_config() must always set sese_enabled=False."""
    from app.modules.render_worker.render_worker import _preview_config

    config = _make_config(sese_enabled=True)
    preview = _preview_config(config)
    assert preview.render.sese_enabled is False
    # Other render settings should still be preserved
    assert preview.render.output_count == 1
    assert preview.render.sese_mode == "auto"


# ──────────────────────────────────────────────────────────────────────────────
# Guard: ratio vs absolute limits
# ──────────────────────────────────────────────────────────────────────────────

def test_ratio_guard_is_binding_when_smaller_than_absolute():
    """
    When ratio * duration < max_seconds, ratio should be the binding constraint.
    timeline_duration=10s, max_sec=8s, max_ratio=0.2 → max_allowed=min(8,2)=2s.
    delta=5s → capped to 2s.
    """
    clips = [_make_clip(start=0.0, end=10.0, duration=10.0)]
    timeline = _make_timeline(clips, target_duration=10.0)
    config = _make_config(
        max_auto_extension_seconds=8.0,
        max_auto_extension_ratio=0.2,
        sese_failure_strategy="trim",
    )

    with patch("app.modules.sese.sese_engine.probe_media_duration", return_value=50.0):
        result = SESEEngine.synchronize(timeline, voice_duration=15.0, config=config)

    meta = getattr(result, "sese_metadata", {})
    assert abs(meta["added_duration"] - 2.0) < 0.01  # ratio bound: 10 * 0.2 = 2.0


def test_absolute_guard_is_binding_when_smaller_than_ratio():
    """
    When max_seconds < ratio * duration, absolute should be binding.
    timeline_duration=20s, max_sec=3s, max_ratio=0.4 → max_allowed=min(3,8)=3s.
    """
    clips = [_make_clip(start=0.0, end=20.0, duration=20.0)]
    timeline = _make_timeline(clips, target_duration=20.0)
    config = _make_config(
        max_auto_extension_seconds=3.0,
        max_auto_extension_ratio=0.4,
        sese_failure_strategy="trim",
    )

    with patch("app.modules.sese.sese_engine.probe_media_duration", return_value=50.0):
        result = SESEEngine.synchronize(timeline, voice_duration=35.0, config=config)

    meta = getattr(result, "sese_metadata", {})
    assert abs(meta["added_duration"] - 3.0) < 0.01  # absolute bound: 3.0s


# ──────────────────────────────────────────────────────────────────────────────
# Review service: _sese_block helper
# ──────────────────────────────────────────────────────────────────────────────

def test_sese_block_extracts_metadata_safely():
    """_sese_block() must handle None, empty dict, and valid sese block."""
    from app.modules.output_review.review_service import _sese_block

    assert _sese_block(None) == {}
    assert _sese_block({}) == {}
    assert _sese_block({"sese": None}) == {}
    assert _sese_block({"sese": "invalid"}) == {}
    result = _sese_block({"sese": {"applied": True, "added_duration": 3.0}})
    assert result["applied"] is True
    assert result["added_duration"] == 3.0


def test_review_service_no_duration_penalty_when_sese_applied(tmp_path):
    """
    When sese.applied=True and added_duration > 0,
    _technical_score must use the adjusted expected_duration,
    preventing a false duration mismatch penalty.
    """
    from app.modules.output_review.review_service import _technical_score
    import app.modules.output_review.review_service as review_svc

    config = _make_config()
    # Simulate a video file
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"fake")

    # Without SESE: duration=13, expected=10 → abs(13-10)=3 > 2 → penalty
    # With SESE applied (+3s): expected_duration=13 → abs(13-13)=0 → no penalty
    log_payload_with_sese = {
        "sese": {
            "applied": True,
            "added_duration": 3.0,
            "trimmed_voice": False,
        }
    }

    fake_media = MagicMock()
    fake_media.width = 1080
    fake_media.height = 1920
    fake_media.duration = 13.0
    fake_media.has_audio = True

    with patch.object(review_svc, "probe_video", return_value=fake_media):
        score_with_sese = _technical_score(
            str(video_path), "success", {}, [], [], config, log_payload_with_sese
        )
        score_without_sese = _technical_score(
            str(video_path), "success", {}, [], [], config, None
        )

    # With SESE → no duration penalty → score = 1.0
    assert score_with_sese == 1.0
    # Without SESE → duration mismatch (3s > 2) → penalized
    assert score_without_sese < 1.0


def test_audio_score_skips_penalty_when_sese_trimmed_voice():
    """
    When sese.applied=True and sese.trimmed_voice=True,
    _audio_score must not penalize voice duration difference.
    """
    from app.modules.output_review.review_service import _audio_score

    config = _make_config()
    # voice_duration=22s, target=10s → diff=12 > 4 → normally would cap to 0.55
    # But SESE trimmed it intentionally → skip penalty
    log_with_sese = {
        "tts": {"provider_used": "edge_tts", "fallback_used": False, "voice_duration": 22.0, "warnings": []},
        "sese": {"applied": True, "trimmed_voice": True},
    }
    output = {"voice_duration": 22.0}
    qa = {}

    score_with_sese = _audio_score(output, log_with_sese, qa, config)

    log_without_sese = {
        "tts": {"provider_used": "edge_tts", "fallback_used": False, "voice_duration": 22.0, "warnings": []},
    }
    score_without_sese = _audio_score(output, log_without_sese, qa, config)

    # With trimmed voice: penalty skipped → score should be higher (1.0)
    assert score_with_sese > score_without_sese
    assert score_with_sese == 1.0
    # Without SESE: diff=12 > 4 → capped to 0.55
    assert abs(score_without_sese - 0.55) < 0.01
