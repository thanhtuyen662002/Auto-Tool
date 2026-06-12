from __future__ import annotations

import os
import sys
from pathlib import Path

from app.local_app.local_config_schema import LocalFrontendStatusData, LocalFrontendStatusResponse
from app.local_app.local_config_service import LocalConfigService
from app.utils.app_paths import frontend_dist_dir


class StaticFrontendService:
    def __init__(self, config_service: LocalConfigService | None = None) -> None:
        self.config_service = config_service or LocalConfigService()

    def get_frontend_dist_path(self) -> Path:
        configured = os.getenv("AUTO_TOOL_FRONTEND_DIST")
        if configured:
            return Path(configured).expanduser().resolve()

        if getattr(sys, "frozen", False):
            return frontend_dist_dir()

        config = self.config_service.load_config()
        path = Path(config.frontend_dist_path).expanduser()
        if not path.is_absolute():
            path = self.config_service.root / path
        return path.resolve()

    def dist_exists(self) -> bool:
        return self.get_frontend_dist_path().is_dir()

    def index_html_exists(self) -> bool:
        return (self.get_frontend_dist_path() / "index.html").is_file()

    def get_static_assets_path(self) -> Path:
        return self.get_frontend_dist_path() / "assets"

    def get_status(self) -> dict[str, object]:
        config = self.config_service.load_config()
        dist_path = self.get_frontend_dist_path()
        dist_exists = dist_path.is_dir()
        index_exists = (dist_path / "index.html").is_file()
        assets_exists = self.get_static_assets_path().is_dir()
        enabled = config.serve_frontend_dist
        ready = enabled and dist_exists and index_exists
        message = (
            "Frontend production build is ready."
            if ready
            else "Frontend build not found. Run scripts/build_frontend.bat first."
            if enabled
            else "Serving the frontend build is disabled in Local App settings."
        )
        return {
            "enabled": enabled,
            "dist_exists": dist_exists,
            "index_html_exists": index_exists,
            "assets_exists": assets_exists,
            "dist_path": str(dist_path),
            "message": message,
        }

    def build_api_response(self) -> LocalFrontendStatusResponse:
        config = self.config_service.load_config()
        status = self.get_status()
        ready = bool(status["enabled"] and status["dist_exists"] and status["index_html_exists"])
        warnings = [] if ready else [str(status["message"])]
        return LocalFrontendStatusResponse(
            success=ready,
            data=LocalFrontendStatusData(
                mode="production_single_port" if config.production_single_port else "development",
                enabled=bool(status["enabled"]),
                dist_exists=bool(status["dist_exists"]),
                index_html_exists=bool(status["index_html_exists"]),
                assets_exists=bool(status["assets_exists"]),
                dist_path=str(status["dist_path"]),
                served_by_backend=ready,
                single_port_url=config.single_port_url,
                message=str(status["message"]),
            ),
            warnings=warnings,
            errors=[],
        )
