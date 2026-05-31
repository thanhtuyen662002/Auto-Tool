from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.project_schema import TTSSettings


class TTSResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    output_path: str
    duration: float | None = None
    format: str
    success: bool
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    fallback_used: bool = False


class TTSProviderInfo(BaseModel):
    id: str
    name: str
    requires_api_key: bool = False
    online: bool
    recommended: bool = False


class TTSVoiceInfo(BaseModel):
    name: str
    language_codes: list[str] = Field(default_factory=list)
    ssml_gender: str = ""
    natural_sample_rate_hertz: int = 0


__all__ = ["TTSProviderInfo", "TTSResult", "TTSSettings", "TTSVoiceInfo"]
