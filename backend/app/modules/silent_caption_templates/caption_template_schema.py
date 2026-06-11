from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SilentCaptionIndustry(str, Enum):
    home_goods = "home_goods"
    kitchen_goods = "kitchen_goods"
    desk_setup = "desk_setup"
    beauty_goods = "beauty_goods"
    storage_organization = "storage_organization"
    dorm_goods = "dorm_goods"
    cleaning_goods = "cleaning_goods"
    general_product = "general_product"


class SilentCaptionIntent(str, Enum):
    hook = "hook"
    product_reveal = "product_reveal"
    unboxing = "unboxing"
    closeup = "closeup"
    demo = "demo"
    benefit = "benefit"
    result = "result"
    cta = "cta"


class SilentCaptionTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    industry: SilentCaptionIndustry
    intent: SilentCaptionIntent
    strategy: str = "all"
    text: str
    tone: str = "natural"
    max_chars: int = Field(default=56, ge=20, le=80)
    requires_product_name: bool = False
    requires_feature: bool = False
    banned_if_no_context: bool = False
    tags: list[str] = Field(default_factory=list)
