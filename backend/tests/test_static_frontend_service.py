from pathlib import Path

from app.local_app import LocalConfigService, StaticFrontendService


def test_static_frontend_status_is_false_when_dist_is_missing(tmp_path: Path) -> None:
    service = StaticFrontendService(LocalConfigService(tmp_path))

    status = service.get_status()

    assert status["enabled"] is True
    assert status["dist_exists"] is False
    assert status["index_html_exists"] is False
    assert "build not found" in str(status["message"]).lower()


def test_static_frontend_status_is_ready_when_build_exists(tmp_path: Path) -> None:
    dist = tmp_path / "frontend" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<div id="root"></div>', encoding="utf-8")
    service = StaticFrontendService(LocalConfigService(tmp_path))

    status = service.get_status()

    assert service.get_frontend_dist_path() == dist.resolve()
    assert status["dist_exists"] is True
    assert status["index_html_exists"] is True
    assert status["assets_exists"] is True
    assert service.build_api_response().success is True
