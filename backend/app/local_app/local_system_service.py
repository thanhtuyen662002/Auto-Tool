from __future__ import annotations

import importlib.util
import platform
import shutil
import sys
from pathlib import Path

from app.local_app.local_config_schema import LocalSystemCheckItem, LocalSystemCheckResponse
from app.local_app.local_config_service import LocalConfigService
from app.local_app.local_paths_service import LocalPathsService
from app.local_app.static_frontend_service import StaticFrontendService
from app.utils.dependency_manager import find_piper_tool, find_piper_voice_files, find_tool


class LocalSystemService:
    def __init__(
        self,
        config_service: LocalConfigService | None = None,
        paths_service: LocalPathsService | None = None,
    ) -> None:
        self.config_service = config_service or LocalConfigService()
        self.paths_service = paths_service or LocalPathsService(self.config_service)

    def check_system(self) -> LocalSystemCheckResponse:
        config = self.config_service.load_config()
        checks = [
            LocalSystemCheckItem(
                name="Python",
                status="ready",
                message=f"Python {platform.python_version()}",
                path=sys.executable,
                version=platform.python_version(),
            ),
            self._command_check("Node.js", "node", required=True),
            self._command_check("npm", "npm", required=True),
            self._managed_tool_check("FFmpeg", "ffmpeg"),
            self._managed_tool_check("ffprobe", "ffprobe"),
            self._output_check(config.default_output_folder),
            self._frontend_dist_check(),
            self._ocr_check(),
            self._piper_check(),
        ]
        required_checks = [item for item in checks if item.required]
        return LocalSystemCheckResponse(
            ready=all(item.status == "ready" for item in required_checks),
            platform=platform.system(),
            checks=checks,
        )

    @staticmethod
    def _command_check(name: str, command: str, required: bool) -> LocalSystemCheckItem:
        path = shutil.which(command)
        if path:
            return LocalSystemCheckItem(
                name=name,
                status="ready",
                message="Available",
                path=path,
                required=required,
            )
        return LocalSystemCheckItem(
            name=name,
            status="missing" if required else "optional",
            message="Not found in PATH",
            required=required,
        )

    @staticmethod
    def _managed_tool_check(name: str, command: str) -> LocalSystemCheckItem:
        path = find_tool(command)
        return LocalSystemCheckItem(
            name=name,
            status="ready" if path else "missing",
            message="Available" if path else "Not installed yet; Local App will download it at startup on Windows",
            path=str(path) if path else None,
        )

    @staticmethod
    def _ocr_check() -> LocalSystemCheckItem:
        available = importlib.util.find_spec("easyocr") is not None
        return LocalSystemCheckItem(
            name="OCR (EasyOCR)",
            status="ready" if available else "optional",
            message="Available" if available else "Optional package; installed automatically when OCR is first prepared",
            required=False,
        )

    @staticmethod
    def _piper_check() -> LocalSystemCheckItem:
        tool = find_piper_tool()
        model, config = find_piper_voice_files()
        available = bool(tool and model and config)
        return LocalSystemCheckItem(
            name="TTS (Piper)",
            status="ready" if available else "optional",
            message="Available" if available else "Optional runtime; installed automatically when local TTS is prepared",
            path=str(tool) if tool else None,
            required=False,
        )

    def _output_check(self, output_folder: str) -> LocalSystemCheckItem:
        path = self.paths_service.resolve_path(output_folder)
        writable = self.paths_service.is_writable_folder(output_folder)
        return LocalSystemCheckItem(
            name="Output folder",
            status="ready" if writable else "missing",
            message="Writable" if writable else "Cannot create or write to this folder",
            path=str(path),
        )

    def _frontend_dist_check(self) -> LocalSystemCheckItem:
        frontend_service = StaticFrontendService(self.config_service)
        index_path = frontend_service.get_frontend_dist_path() / "index.html"
        return LocalSystemCheckItem(
            name="Frontend build",
            status="ready" if index_path.exists() else "warning",
            message="Built frontend is available" if index_path.exists() else "Run the frontend build script before packaging",
            path=str(index_path),
            required=False,
        )
