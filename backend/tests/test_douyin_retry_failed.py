from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.api import create_app
from app.modules.douyin_reup.douyin_reup_service import DouyinReupService, build_retry_cache
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, DouyinVideoItem, SubtitleSourceResult, TranslationResult
from app.schemas.project_schema import ProjectConfig


def _config(source_dir: Path, output_dir: Path) -> ProjectConfig:
    return ProjectConfig.model_validate(
        {
            "project_name": "douyin-retry-test",
            "source_folder": str(source_dir),
            "output_folder": str(output_dir),
            "product": {"name": "x", "brand": "", "description": "x", "features": ["x"], "cta": "x"},
            "render": {"output_count": 1, "duration": 8, "aspect_ratio": "9:16", "resolution": "1080x1920", "fps": 30},
            "effects": {"cut_intensity": 0, "speed_variation": 0, "grain": 0, "zoom_motion": 0, "overlay_height": 22, "subtitle_size": 54},
            "ai": {"text_model": "mock", "tone": "translator", "language": "vi", "gemini_api_keys": []},
            "douyin_reup": DouyinReupSettings(
                enabled=True,
                review_subtitles_before_render=False,
                auto_render_after_translation=True,
            ).model_dump(mode="json"),
        }
    )


def test_retry_failed_api_queues_only_failed_outputs(tmp_path: Path, monkeypatch):
    database.DB_PATH = tmp_path / "retry-api.db"
    database.init_db()
    project = _config(tmp_path / "source", tmp_path / "out")
    database.create_project("project-retry", project.model_dump(mode="json"))
    database.create_job("job-original", "project-retry", preview_only=False, total_outputs=2)
    database.update_job(
        "job-original",
        results_json='{"outputs":[{"index":1,"status":"success","path":"ok.mp4","source_video":"ok.mp4"},{"index":2,"status":"failed","path":"","source_video":"bad.mp4","failed_step":"render"}]}',
    )
    monkeypatch.setattr("app.api.run_douyin_reup_retry_job", lambda *args, **kwargs: None)

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/douyin-reup/jobs/job-original/retry-failed",
            json={"retry_steps": ["render"], "settings": {}},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["retry_outputs"] == 1


def test_retry_custom_read_screen_text_queues_selected_output_with_ocr_priority(tmp_path: Path, monkeypatch):
    database.DB_PATH = tmp_path / "retry-custom-api.db"
    database.init_db()
    project = _config(tmp_path / "source", tmp_path / "out")
    database.create_project("project-retry-custom", project.model_dump(mode="json"))
    database.create_job("job-custom", "project-retry-custom", preview_only=False, total_outputs=2)
    database.update_job(
        "job-custom",
        results_json=json.dumps(
            {
                "outputs": [
                    {"index": 1, "status": "success", "path": "ok.mp4", "source_video": "ok.mp4"},
                    {"index": 2, "status": "failed", "path": "", "source_video": "bad.mp4", "failed_step": "render"},
                ]
            }
        ),
    )
    monkeypatch.setattr("app.api.start_background_dependency_warmup", lambda **_kwargs: None)
    captured = {}
    monkeypatch.setattr(
        "app.api._queue_douyin_retry_failed_job",
        lambda **kwargs: captured.update(kwargs) or "job-custom-retry",
    )

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/douyin-reup/jobs/job-custom/retry-custom",
            json={
                "retry_mode": "read_screen_text",
                "video_ids": ["video_001"],
                "include_unfinished": False,
                "settings": {
                    "subtitle_source_priority": ["sidecar_srt", "embedded_subtitle", "asr", "ocr_hardsub"],
                    "ocr_region_mode": "full_frame",
                },
            },
        )

    assert response.status_code == 200
    assert response.json()["job_id"] == "job-custom-retry"
    assert response.json()["retry_outputs"] == 1
    assert captured["failed_outputs"][0]["source_video"] == "ok.mp4"
    assert captured["retry_steps"] == {"subtitle_source", "ocr", "translation", "render"}
    settings_override = captured["settings_override"]
    assert settings_override["use_ocr_if_no_subtitle"] is True
    assert settings_override["use_ocr_if_asr_failed"] is True
    assert settings_override["prefer_ocr_over_asr_when_text_visible"] is True
    assert settings_override["subtitle_source_priority"].index("ocr_hardsub") < settings_override["subtitle_source_priority"].index("asr")


def test_retry_failed_reuses_existing_source_and_translation_for_render_retry(tmp_path: Path):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "out"
    source_dir.mkdir()
    video = source_dir / "clip.mp4"
    source_srt = tmp_path / "source.srt"
    translated_srt = tmp_path / "translated.srt"
    video.write_bytes(b"fake")
    source_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nNi hao\n", encoding="utf-8")
    translated_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nXin chao\n", encoding="utf-8")
    calls = {"detector": 0, "translator": 0, "render": 0}

    class FakeScanner:
        def scan_folder(self, _folder):
            return [
                DouyinVideoItem(path=str(video), filename=video.name, duration=8, width=1080, height=1920, fps=30, has_audio=True, embedded_subtitle_found=False)
            ]

    class DetectorMustNotRun:
        def detect_source(self, *_args, **_kwargs):
            calls["detector"] += 1
            raise AssertionError("source detector should not run when source_srt_file exists")

    class TranslatorMustNotRun:
        def translate_srt(self, *_args, **_kwargs):
            calls["translator"] += 1
            raise AssertionError("translator should not run when translated_srt_file exists")

    class FakePipeline:
        def render_video_with_translated_subtitle(self, video, translation_result, settings, output_dir, output_name):
            calls["render"] += 1
            output = Path(output_dir) / output_name
            output.write_bytes(b"fake mp4")
            return {"path": str(output), "duration": 8, "warnings": [], "errors": []}

    failed_output = {
        "index": 1,
        "status": "failed",
        "source_video": str(video),
        "subtitle_source": "sidecar_srt",
        "source_srt_file": str(source_srt),
        "translated_srt_file": str(translated_srt),
        "failed_step": "render",
    }
    summary = DouyinReupService(
        scanner=FakeScanner(),
        source_detector=DetectorMustNotRun(),
        translator=TranslatorMustNotRun(),
        render_pipeline=FakePipeline(),
    ).process_folder(
        _config(source_dir, output_dir),
        retry_cache=build_retry_cache([failed_output]),
        retry_steps={"render"},
    )

    assert summary["rendered"] == 1
    assert calls == {"detector": 0, "translator": 0, "render": 1}


def test_retry_read_screen_text_reruns_source_and_translation_even_when_cache_exists(tmp_path: Path):
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "out"
    source_dir.mkdir()
    video = source_dir / "clip.mp4"
    cached_source_srt = tmp_path / "cached-source.srt"
    cached_translated_srt = tmp_path / "cached-translated.srt"
    video.write_bytes(b"fake")
    cached_source_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nCached\n", encoding="utf-8")
    cached_translated_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nCache cu\n", encoding="utf-8")
    calls = {"detector": 0, "translator": 0, "render": 0}

    class FakeScanner:
        def scan_folder(self, _folder):
            return [
                DouyinVideoItem(path=str(video), filename=video.name, duration=8, width=1080, height=1920, fps=30, has_audio=True, embedded_subtitle_found=False)
            ]

    class FakeDetector:
        def detect_source(self, _video, settings, detected_output_dir, **_kwargs):
            calls["detector"] += 1
            fresh_source = Path(detected_output_dir) / "fresh-source.srt"
            fresh_source.write_text("1\n00:00:00,000 --> 00:00:01,000\nFresh OCR\n", encoding="utf-8")
            return SubtitleSourceResult(
                video_path=str(video),
                source_type="ocr_hardsub",
                source_srt_path=str(fresh_source),
                language=settings.source_language,
                ocr_frame_count=3,
                ocr_detected_line_count=1,
                ocr_average_confidence=0.8,
                ocr_region_mode=settings.ocr_region_mode,
            )

    class FakeTranslator:
        def translate_srt(self, source_srt_path, translated_path, **_kwargs):
            calls["translator"] += 1
            assert source_srt_path != str(cached_source_srt)
            Path(translated_path).write_text("1\n00:00:00,000 --> 00:00:01,000\nBan moi\n", encoding="utf-8")
            return TranslationResult(
                source_srt_path=source_srt_path,
                translated_srt_path=str(translated_path),
                provider="fake",
            )

    class FakePipeline:
        def render_video_with_translated_subtitle(self, video, translation_result, settings, output_dir, output_name):
            calls["render"] += 1
            assert translation_result.translated_srt_path != str(cached_translated_srt)
            output = Path(output_dir) / output_name
            output.write_bytes(b"fake mp4")
            return {"path": str(output), "duration": 8, "warnings": [], "errors": []}

    cached_output = {
        "index": 1,
        "status": "failed",
        "source_video": str(video),
        "subtitle_source": "sidecar_srt",
        "source_srt_file": str(cached_source_srt),
        "translated_srt_file": str(cached_translated_srt),
        "failed_step": "render",
    }
    summary = DouyinReupService(
        scanner=FakeScanner(),
        source_detector=FakeDetector(),
        translator=FakeTranslator(),
        render_pipeline=FakePipeline(),
    ).process_folder(
        _config(source_dir, output_dir),
        retry_cache=build_retry_cache([cached_output]),
        retry_steps={"subtitle_source", "ocr", "translation", "render"},
    )

    assert summary["rendered"] == 1
    assert calls == {"detector": 1, "translator": 1, "render": 1}
