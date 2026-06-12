from pathlib import Path

from app.api import create_app
from app.local_app import LocalAppConfig, LocalConfigService, LocalPathsService


def test_local_config_is_created_and_recovers_from_invalid_json(tmp_path: Path) -> None:
    service = LocalConfigService(tmp_path)

    config = service.load_config()
    assert config.default_output_folder == "./examples/outputs"
    assert service.config_path.exists()

    service.config_path.write_text("{broken", encoding="utf-8")
    recovered = service.load_config()

    assert recovered == LocalAppConfig()
    assert list(service.config_dir.glob("local_app_config.invalid-*.bak"))


def test_recent_paths_are_normalized_deduplicated_and_limited(tmp_path: Path) -> None:
    config_service = LocalConfigService(tmp_path)
    config_service.save_config(LocalAppConfig(max_recent_items=2))
    paths_service = LocalPathsService(config_service)

    paths_service.add_recent_path("source", "one")
    paths_service.add_recent_path("source", "two")
    recent = paths_service.add_recent_path("source", "one")

    assert recent.source_folders == [
        str((tmp_path / "one").resolve()),
        str((tmp_path / "two").resolve()),
    ]


def test_local_app_routes_are_registered(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTO_TOOL_ROOT", str(tmp_path))
    route_paths = {route.path for route in create_app().routes}

    assert {
        "/api/local-app/config",
        "/api/local-app/system-check",
        "/api/local-app/frontend-status",
        "/api/local-app/recent-paths",
        "/api/local-app/recent-paths/source",
        "/api/local-app/recent-paths/output",
        "/api/local-app/recent-paths/music",
        "/api/local-app/open-folder",
        "/api/local-app/reveal-file",
    }.issubset(route_paths)
