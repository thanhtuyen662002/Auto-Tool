from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LocalAppConfig(BaseModel):
    default_source_folder: str = ""
    default_output_folder: str = "./examples/outputs"
    default_music_folder: str = ""
    auto_open_browser: bool = True
    enable_open_folder: bool = True
    max_recent_items: int = Field(default=5, ge=1, le=20)
    backend_host: str = "127.0.0.1"
    backend_port: int = Field(default=8000, ge=1, le=65535)
    frontend_host: str = "127.0.0.1"
    frontend_port: int = Field(default=5173, ge=1, le=65535)
    production_single_port: bool = True
    serve_frontend_dist: bool = True
    single_port_url: str = "http://127.0.0.1:8000"
    frontend_dist_path: str = "frontend/dist"


class LocalPathRequest(BaseModel):
    path: str = Field(min_length=1)


class LocalRecentPaths(BaseModel):
    source_folders: list[str] = Field(default_factory=list)
    output_folders: list[str] = Field(default_factory=list)
    music_folders: list[str] = Field(default_factory=list)


class LocalDesktopActionResponse(BaseModel):
    success: bool
    path: str
    message: str


class LocalSystemCheckItem(BaseModel):
    name: str
    status: Literal["ready", "missing", "optional", "warning"]
    message: str
    path: str | None = None
    version: str | None = None
    required: bool = True


class LocalSystemCheckResponse(BaseModel):
    ready: bool
    platform: str
    checks: list[LocalSystemCheckItem]


class LocalFrontendStatusData(BaseModel):
    mode: Literal["production_single_port", "development"]
    enabled: bool
    dist_exists: bool
    index_html_exists: bool
    assets_exists: bool
    dist_path: str
    served_by_backend: bool
    single_port_url: str
    message: str


class LocalFrontendStatusResponse(BaseModel):
    success: bool
    data: LocalFrontendStatusData
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
