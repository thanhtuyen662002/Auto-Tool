from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RenderResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(gt=0)
    path: str
    status: str
    duration: float | None = None
    error: str | None = None
