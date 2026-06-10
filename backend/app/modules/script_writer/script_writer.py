from __future__ import annotations

import os

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.adapters.gemini_adapter import GeminiAdapter, ScriptGenerationError
from app.modules.industry_presets.industry_preset_service import IndustryPresetService
from app.modules.industry_presets.industry_schema import IndustryPreset
from app.modules.script_writer.prompts import (
    build_product_video_script_prompt,
    recommended_line_count,
    variant_angle,
)
from app.schemas.project_schema import ProjectConfig
from app.utils.logger import get_logger


logger = get_logger(__name__)


def _industry_for_config(config: ProjectConfig) -> IndustryPreset | None:
    if not config.industry or not config.industry.preset_id:
        return None
    return IndustryPresetService().get_preset(config.industry.preset_id)


class VoiceoverLine(BaseModel):
    model_config = ConfigDict(extra="ignore")

    time_hint: str = ""
    text: str = Field(min_length=1)


class SubtitleLine(BaseModel):
    model_config = ConfigDict(extra="ignore")

    start_hint: float | None = None
    end_hint: float | None = None
    text: str = Field(min_length=1)


class ProductVideoScript(BaseModel):
    model_config = ConfigDict(extra="ignore")

    variant_style_id: str | None = None
    industry_preset_id: str | None = None
    caption_tone: str | None = None
    hashtag_suggestions_used: list[str] = Field(default_factory=list)
    hook: str = Field(min_length=1)
    voiceover: list[VoiceoverLine] = Field(min_length=1)
    subtitles: list[SubtitleLine] = Field(min_length=1)
    cta: str = Field(min_length=1)
    caption: str = Field(min_length=1)
    hashtags: list[str] = Field(default_factory=list)


class ScriptWriter:
    def __init__(self, gemini_adapter: GeminiAdapter | None = None) -> None:
        self.gemini_adapter = gemini_adapter
        self.warnings: list[str] = []

    def generate_script(self, config: ProjectConfig, output_index: int = 1) -> ProductVideoScript:
        self.warnings = []
        industry = _industry_for_config(config)
        prompt = build_product_video_script_prompt(
            config.product,
            config.render,
            config.ai,
            output_index,
            industry=industry,
        )
        adapter = self.gemini_adapter or GeminiAdapter(
            api_key=None,
            model_name=config.ai.text_model,
            api_keys=config.ai.gemini_api_keys,
            start_index=output_index - 1,
        )

        try:
            raw_script = adapter.generate_json(prompt)
            script = ProductVideoScript.model_validate(raw_script)
        except (Exception, ValidationError) as exc:
            message = f"Gemini tạo kịch bản lỗi cho video {output_index:03d}: {exc}"
            if not self._fallback_enabled():
                raise ScriptGenerationError(message) from exc

            warning = f"{message}; đang dùng kịch bản dự phòng vì AUTO_TOOL_ALLOW_SCRIPT_FALLBACK=1"
            logger.warning(warning)
            self.warnings.append(warning)
            script = self._fallback_script(config, output_index, industry)

        return self._prepare_script(script, config)

    def _prepare_script(
        self,
        script: ProductVideoScript,
        config: ProjectConfig,
    ) -> ProductVideoScript:
        target_duration = float(config.render.duration)
        industry = _industry_for_config(config)
        voiceover = [line for line in script.voiceover if line.text.strip()]
        needed_count = recommended_line_count(target_duration)
        max_count = needed_count + 1

        if not voiceover:
            raise ScriptGenerationError("Kịch bản AI trả về phải có ít nhất một dòng giọng đọc.")

        if len(voiceover) > max_count:
            voiceover = voiceover[:max_count]

        cta = script.cta.strip()
        voiceover = self._apply_even_timing(voiceover, target_duration)
        subtitles = [
            SubtitleLine(
                start_hint=self._parse_start(line.time_hint),
                end_hint=self._parse_end(line.time_hint),
                text=line.text,
            )
            for line in voiceover
        ]

        return script.model_copy(
            update={
                "industry_preset_id": script.industry_preset_id or (industry.id if industry else None),
                "caption_tone": script.caption_tone or (industry.caption_tone if industry else None),
                "hashtag_suggestions_used": (
                    list(script.hashtag_suggestions_used)
                    or (list(industry.hashtag_suggestions) if industry else [])
                ),
                "hook": script.hook.strip(),
                "voiceover": voiceover,
                "subtitles": subtitles,
                "cta": cta or script.cta,
                "caption": script.caption.strip(),
                "hashtags": list(script.hashtags) or (list(industry.hashtag_suggestions[:6]) if industry else []),
            }
        )

    @staticmethod
    def _fallback_script(
        config: ProjectConfig,
        output_index: int,
        industry: IndustryPreset | None = None,
    ) -> ProductVideoScript:
        line_count = recommended_line_count(float(config.render.duration))
        lines = ScriptWriter._fallback_voiceover_lines(config, output_index)[:line_count]
        hashtags = list(industry.hashtag_suggestions[:6]) if industry else ["#review", "#sanpham", "#muasam"]
        caption = (
            f"{config.product.name}: {industry.caption_tone}"
            if industry
            else f"Một góc nhìn nhanh về {config.product.name}."
        )
        fallback = {
            "industry_preset_id": industry.id if industry else None,
            "caption_tone": industry.caption_tone if industry else None,
            "hashtag_suggestions_used": hashtags,
            "hook": f"{config.product.name} có vài điểm đáng xem trong nhu cầu sử dụng hằng ngày",
            "voiceover": [{"time_hint": "", "text": text} for text in lines],
            "subtitles": [{"start_hint": None, "end_hint": None, "text": text} for text in lines],
            "cta": config.product.cta,
            "caption": f"Một góc nhìn nhanh về {config.product.name}.",
            "hashtags": hashtags,
            "caption": caption,
        }
        return ProductVideoScript.model_validate(fallback)

    @staticmethod
    def _fallback_voiceover_lines(config: ProjectConfig, output_index: int) -> list[str]:
        product = config.product
        features = [feature.strip() for feature in product.features if feature.strip()]
        if not features:
            features = ["thiết kế dễ dùng", "phù hợp nhiều nhu cầu", "trải nghiệm tiện lợi"]

        angle = variant_angle(output_index)
        pool = [
            f"Nếu bạn đang tìm một sản phẩm dễ dùng hằng ngày, {product.name} là lựa chọn đáng để xem qua.",
            f"Biến thể này tập trung vào {angle}, nên phần review sẽ đi thẳng vào trải nghiệm thực tế.",
            f"Sản phẩm đến từ {product.brand}, với mô tả chính là {product.description}",
            f"Điểm đầu tiên cần nhắc đến là {features[0]}, phù hợp khi bạn muốn thao tác nhanh và gọn.",
            f"Thêm một điểm đáng chú ý là {features[1 % len(features)]}, giúp sản phẩm dễ dùng trong nhiều hoàn cảnh.",
            f"Nếu dùng ở nhà hoặc văn phòng, {features[2 % len(features)]} là chi tiết tạo cảm giác tiện hơn.",
            "Với nhu cầu mua sắm online, những điểm này giúp bạn dễ hình dung sản phẩm trước khi quyết định.",
            "Bạn nên xem kỹ thông tin shop cung cấp để chọn đúng phiên bản và phụ kiện đi kèm.",
            product.cta,
            f"Tóm lại, {product.name} phù hợp nếu bạn cần một lựa chọn gọn gàng và thực tế.",
            "Hãy cân nhắc các điểm nổi bật này với nhu cầu sử dụng của bạn trước khi đặt mua.",
        ]

        offset = (max(1, output_index) - 1) % len(pool)
        return pool[offset:] + pool[:offset]

    @staticmethod
    def _apply_even_timing(lines: list[VoiceoverLine], target_duration: float) -> list[VoiceoverLine]:
        if not lines:
            return []

        slot = target_duration / len(lines)
        timed: list[VoiceoverLine] = []
        for index, line in enumerate(lines):
            start = round(index * slot, 3)
            end = round(target_duration if index == len(lines) - 1 else (index + 1) * slot, 3)
            timed.append(
                VoiceoverLine(
                    time_hint=f"{start:g}-{end:g}s",
                    text=line.text.strip(),
                )
            )
        return timed

    @staticmethod
    def _parse_start(time_hint: str) -> float:
        return float(time_hint.split("-", 1)[0].replace("s", "").strip())

    @staticmethod
    def _parse_end(time_hint: str) -> float:
        return float(time_hint.split("-", 1)[1].replace("s", "").strip())

    @staticmethod
    def _fallback_enabled() -> bool:
        value = os.getenv("AUTO_TOOL_ALLOW_SCRIPT_FALLBACK", "0").strip().lower()
        return value in {"1", "true", "yes", "on"}
