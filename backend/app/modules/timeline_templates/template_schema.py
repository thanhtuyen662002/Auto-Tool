from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.timeline_builder.timeline_builder import TimelineClip


TextRole = Literal["hook", "product", "demo", "benefit", "cta"]
EnergyLevel = Literal["low", "medium", "high"]


class TimelineSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    start_ratio: float = Field(ge=0, le=1)
    end_ratio: float = Field(ge=0, le=1)
    preferred_tags: list[str] = Field(default_factory=list)
    avoided_tags: list[str] = Field(default_factory=list)
    min_clip_duration: float = Field(default=0.8, gt=0)
    max_clip_duration: float = Field(default=3.0, gt=0)
    energy_level: EnergyLevel = "medium"
    text_role: TextRole

    @model_validator(mode="after")
    def validate_slot(self) -> "TimelineSlot":
        if self.end_ratio <= self.start_ratio:
            raise ValueError("end_ratio must be greater than start_ratio")
        if self.max_clip_duration < self.min_clip_duration:
            raise ValueError("max_clip_duration must be greater than or equal to min_clip_duration")
        return self


class TimelineTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    supported_durations: list[int] = Field(default_factory=list)
    slots: list[TimelineSlot] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_slots(self) -> "TimelineTemplate":
        previous_end = 0.0
        for slot in self.slots:
            if slot.start_ratio < previous_end - 0.0001:
                raise ValueError(f"Template slots overlap or are out of order near '{slot.name}'")
            previous_end = slot.end_ratio
        if self.slots[0].start_ratio > 0.0001:
            raise ValueError("Template must start at ratio 0")
        if abs(self.slots[-1].end_ratio - 1.0) > 0.0001:
            raise ValueError("Template must end at ratio 1")
        return self


class TimelinePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str
    output_index: int = Field(gt=0)
    target_duration: float = Field(gt=0)
    slots: list[TimelineSlot]
    selected_clips: list[TimelineClip]

