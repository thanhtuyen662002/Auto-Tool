from __future__ import annotations

from copy import deepcopy

from app.modules.final_output_qa.final_output_qa_schema import PlatformTarget


_COMMON = {
    "preferred_aspect_ratio": "9:16",
    "preferred_resolution": "1080x1920",
    "min_duration": 3,
    "preferred_fps": [24, 25, 30, 60],
    "preferred_codecs": ["h264"],
    "preferred_audio_codecs": ["aac"],
}

_PROFILES = {
    PlatformTarget.tiktok: {
        **_COMMON,
        "id": "tiktok",
        "name": "TikTok",
        "max_duration_warning": 180,
        "max_file_size_mb_warning": 500,
    },
    PlatformTarget.instagram_reels: {
        **_COMMON,
        "id": "instagram_reels",
        "name": "Instagram Reels",
        "max_duration_warning": 90,
        "max_file_size_mb_warning": 300,
    },
    PlatformTarget.youtube_shorts: {
        **_COMMON,
        "id": "youtube_shorts",
        "name": "YouTube Shorts",
        "max_duration_warning": 180,
        "max_file_size_mb_warning": 500,
    },
    PlatformTarget.generic_vertical: {
        **_COMMON,
        "id": "generic_vertical",
        "name": "Generic Vertical",
        "max_duration_warning": 180,
        "max_file_size_mb_warning": 500,
    },
}


def get_platform_profile(target: PlatformTarget | str) -> dict:
    platform = target if isinstance(target, PlatformTarget) else PlatformTarget(target)
    return deepcopy(_PROFILES[platform])


def list_platform_profiles() -> list[dict]:
    return [deepcopy(profile) for profile in _PROFILES.values()]
