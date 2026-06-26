from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class TimeSlotModel(BaseModel):
    id: int | None = None
    channel_id: str | None = None
    posting_time: str
    active: int = 1


class ChannelCreateRequest(BaseModel):
    id: str | None = None  # If empty, a UUID will be generated
    platform: str  # 'youtube', 'meta', 'tiktok'
    channel_name: str
    channel_avatar: str | None = None
    auth_data: dict[str, Any]
    daily_limit: int = 5
    time_slots: list[str] = []  # List of 'HH:MM' strings


class ChannelResponse(BaseModel):
    id: str
    platform: str
    channel_name: str
    channel_avatar: str | None = None
    auth_data: dict[str, Any]
    daily_limit: int
    status: str
    created_at: str
    time_slots: list[TimeSlotModel] = []


class ProductAffiliateCreate(BaseModel):
    id: str | None = None
    product_name: str
    product_tag: str
    affiliate_link: str
    description: str | None = None


class ProductAffiliateResponse(BaseModel):
    id: str
    product_name: str
    product_tag: str
    affiliate_link: str
    description: str | None = None
    created_at: str


class QueueItemResponse(BaseModel):
    id: str
    channel_id: str
    channel_name: str
    platform: str
    video_path: str
    title: str
    caption: str | None = None
    hashtags: str | None = None
    product_link: str | None = None
    scheduled_time: str
    status: str
    error_message: str | None = None
    created_at: str


class QueueItemUpdateRequest(BaseModel):
    title: str | None = None
    caption: str | None = None
    hashtags: str | None = None
    product_link: str | None = None
    scheduled_time: str | None = None
    status: str | None = None


class QueueReorderRequest(BaseModel):
    queue_ids: list[str]


class QueueGenerateRequest(BaseModel):
    folder_path: str
    channel_ids: list[str]
    tags: list[str] | None = None
