from __future__ import annotations

import pytest
from app.modules.douyin_reup.douyin_render_pipeline import DouyinRenderPipeline
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, DouyinVideoItem

def test_render_pipeline_aspect_ratio_logic(monkeypatch):
    captured_args = []
    
    def mock_run_ffmpeg(args):
        captured_args.append(args)
        
    monkeypatch.setattr("app.modules.douyin_reup.douyin_render_pipeline.run_ffmpeg", mock_run_ffmpeg)
    
    pipeline = DouyinRenderPipeline()
    
    # 1. Test Case: Mismatched aspect ratio (Landscape video into Vertical canvas)
    video_landscape = DouyinVideoItem(
        path="landscape.mp4",
        filename="landscape.mp4",
        duration=10.0,
        width=1920,
        height=1080,
        fps=30.0,
        has_audio=True
    )
    
    settings_vertical = DouyinReupSettings(
        resolution="1920x1080",  # Will be swapped to 1080x1920 due to "vertical" mode
        video_dimension_mode="vertical",
        keep_original_audio=True,
        add_bgm=False
    )
    
    # Run render
    pipeline._run_render(
        video=video_landscape,
        settings=settings_vertical,
        output_path="output_vertical.mp4",
        width=1080,  # calculated target width
        height=1920, # calculated target height
        overlay_path=None,
        subtitle_ass_path=None,
        bgm_path=None
    )
    
    assert len(captured_args) == 1
    args = captured_args[0]
    
    # Verify that the filter_complex contains split, boxblur, and overlay because aspect ratios differ
    filter_complex = ""
    for i, arg in enumerate(args):
        if arg == "-filter_complex":
            filter_complex = args[i+1]
            break
            
    assert "split=2" in filter_complex
    assert "boxblur" in filter_complex
    assert "overlay=(W-w)/2:(H-h)/2" in filter_complex
    assert "scale=1080:1920" in filter_complex
    
    # 2. Test Case: Matching aspect ratio (Vertical video into Vertical canvas)
    captured_args.clear()
    video_vertical = DouyinVideoItem(
        path="vertical.mp4",
        filename="vertical.mp4",
        duration=10.0,
        width=1080,
        height=1920,
        fps=30.0,
        has_audio=True
    )
    
    pipeline._run_render(
        video=video_vertical,
        settings=settings_vertical,
        output_path="output_vertical_match.mp4",
        width=1080,
        height=1920,
        overlay_path=None,
        subtitle_ass_path=None,
        bgm_path=None
    )
    
    assert len(captured_args) == 1
    args = captured_args[0]
    
    filter_complex = ""
    for i, arg in enumerate(args):
        if arg == "-filter_complex":
            filter_complex = args[i+1]
            break
            
    # Should use the matching aspect ratio crop-to-fill, no split, boxblur, or overlay
    assert "split=2" not in filter_complex
    assert "boxblur" not in filter_complex
    assert "overlay" not in filter_complex
    assert "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" in filter_complex
