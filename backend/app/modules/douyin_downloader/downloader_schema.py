from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class DouyinDownloaderStatusResponse(BaseModel):
    browser_open: bool = False
    logged_in: bool = False
    chrome_path: str | None = None
    driver_path: str | None = None
    profile_dir: str
    current_url: str | None = None
    page_title: str | None = None
    message: str


class DouyinDownloaderOpenRequest(BaseModel):
    start_url: str | None = "https://www.douyin.com/"


class DouyinDownloaderCloseResponse(BaseModel):
    success: bool
    message: str


class DouyinDownloaderScanRequest(BaseModel):
    channel_url: str = Field(min_length=1)
    max_scrolls: int = Field(default=5000, ge=1, le=5000)
    scan_until_end: bool = True


class DouyinDownloaderDownloadRequest(BaseModel):
    links: list[str] = Field(default_factory=list)
    output_folder: str = Field(min_length=1)
    skip_existing: bool = True
    channel_url: str | None = None

    @field_validator("links")
    @classmethod
    def clean_links(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in value:
            link = str(item).strip()
            if not link or link in seen:
                continue
            cleaned.append(link)
            seen.add(link)
        return cleaned


class DouyinDownloaderOutputItem(BaseModel):
    link: str
    title: str | None = None
    path: str | None = None
    status: Literal["success", "failed", "skipped", "paused"] = "success"
    message: str = ""


class DouyinDownloaderJobResponse(BaseModel):
    job_id: str
    job_type: Literal["scan", "download"]
    status: Literal["queued", "running", "paused", "completed", "failed"]
    current_step: str
    progress: int = Field(ge=0, le=100)
    total_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    output_folder: str | None = None
    skip_existing: bool = True
    pause_requested: bool = False
    links: list[str] = Field(default_factory=list)
    outputs: list[DouyinDownloaderOutputItem] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class DouyinDownloaderChannelDownloadHistory(BaseModel):
    channel_url: str
    output_folder: str | None = None
    links: list[str] = Field(default_factory=list)
    total_links: int = 0
    updated_at: str | None = None


class DouyinDownloaderHistoryResponse(BaseModel):
    recent_channel_urls: list[str] = Field(default_factory=list)
    recent_output_folders: list[str] = Field(default_factory=list)
    recent_jobs: list[DouyinDownloaderJobResponse] = Field(default_factory=list)
    downloaded_links: dict[str, DouyinDownloaderOutputItem] = Field(default_factory=dict)
    scanned_channels: dict[str, list[str]] = Field(default_factory=dict)
    channel_downloads: dict[str, DouyinDownloaderChannelDownloadHistory] = Field(default_factory=dict)


class DouyinDownloaderJobActionResponse(BaseModel):
    success: bool
    message: str
    job: DouyinDownloaderJobResponse
