from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.adapters.gemini_adapter import GeminiAdapter, ScriptGenerationError
from app.modules.script_variants.variant_prompt_builder import build_script_variant_prompt
from app.modules.script_variants.variant_registry import VariantPlanner, get_variant_style
from app.modules.script_variants.variant_schema import (
    ScriptVariantRequest,
    ScriptVariantResult,
    ScriptVariantStyle,
)
from app.modules.script_writer.script_writer import ProductVideoScript, ScriptWriter
from app.schemas.project_schema import ProjectConfig
from app.utils.file_utils import write_json
from app.utils.logger import get_logger


logger = get_logger(__name__)
PLACEHOLDER_PATTERN = re.compile(r"\{[a-zA-Z0-9_]+\}")


class ScriptVariantGenerator:
    def __init__(self, gemini_adapter: GeminiAdapter | None = None) -> None:
        self.gemini_adapter = gemini_adapter
        self.warnings: list[str] = []
        self.results: list[ScriptVariantResult] = []

    def generate_variants(
        self,
        config: ProjectConfig,
        output_count: int,
        timeline_template_id: str | None = None,
    ) -> list[ProductVideoScript]:
        self.warnings = []
        self.results = []
        planned_styles = VariantPlanner().plan_variants(output_count, timeline_template_id)
        scripts: list[ProductVideoScript] = []

        for output_index, style in enumerate(planned_styles, start=1):
            result = self._generate_one(config, output_count, output_index, timeline_template_id, style)
            self.results.append(result)
            scripts.append(self._to_product_script(result, config))

        return scripts

    def write_report(
        self,
        output_dir: str | Path,
        config: ProjectConfig,
    ) -> str:
        path = Path(output_dir) / "script_variants.json"
        write_json(path, build_script_variants_report(config, self.results))
        return str(path)

    def _generate_one(
        self,
        config: ProjectConfig,
        total_outputs: int,
        output_index: int,
        timeline_template_id: str | None,
        style: ScriptVariantStyle,
    ) -> ScriptVariantResult:
        request = ScriptVariantRequest(
            output_index=output_index,
            total_outputs=total_outputs,
            product=config.product,
            render_duration=config.render.duration,
            timeline_template_id=timeline_template_id,
            variant_style_id=style.id,
            language=config.ai.language,
        )
        adapter = self.gemini_adapter or GeminiAdapter(
            api_key=None,
            model_name=config.ai.text_model,
            api_keys=config.ai.gemini_api_keys,
            start_index=output_index - 1,
        )

        try:
            raw_result = adapter.generate_json(build_script_variant_prompt(request, style))
            raw_result["output_index"] = output_index
            raw_result["variant_style_id"] = style.id
            result = ScriptVariantResult.model_validate(raw_result)
            self._validate_result(result)
            return result
        except (Exception, ValidationError) as exc:
            warning = (
                f"Script variant generation failed for output {output_index:03d} "
                f"style={style.id}: {exc}; using style-specific fallback."
            )
            logger.warning(warning)
            self.warnings.append(warning)
            return self._fallback_result(config, output_index, style)

    def _to_product_script(self, result: ScriptVariantResult, config: ProjectConfig) -> ProductVideoScript:
        raw_script = ProductVideoScript.model_validate(result.model_dump(mode="json"))
        prepared = ScriptWriter()._prepare_script(raw_script, config)
        return prepared.model_copy(update={"variant_style_id": result.variant_style_id})

    def _fallback_result(
        self,
        config: ProjectConfig,
        output_index: int,
        style: ScriptVariantStyle,
    ) -> ScriptVariantResult:
        fallback = _fallback_payload(config, style, output_index)
        fallback["output_index"] = output_index
        fallback["variant_style_id"] = style.id
        return ScriptVariantResult.model_validate(fallback)

    @staticmethod
    def _validate_result(result: ScriptVariantResult) -> None:
        payload = result.model_dump(mode="json")
        placeholders = _find_placeholders(payload)
        if placeholders:
            raise ScriptGenerationError(f"Script contains unresolved placeholders: {', '.join(placeholders)}")

        for line in result.voiceover:
            if len(line.text) > 260:
                raise ScriptGenerationError("Voiceover line is unusually long.")


def build_script_variants_report(
    config: ProjectConfig,
    variants: list[ScriptVariantResult],
) -> dict[str, Any]:
    return {
        "project_name": config.project_name,
        "total_variants": len(variants),
        "variants": [variant.model_dump(mode="json") for variant in variants],
    }


def _fallback_payload(config: ProjectConfig, style: ScriptVariantStyle, output_index: int) -> dict[str, Any]:
    product = config.product
    feature = product.features[(output_index - 1) % len(product.features)]
    second_feature = product.features[output_index % len(product.features)]
    common_hashtags = ["#review", "#sanpham", "#muasam"]
    payloads: dict[str, dict[str, Any]] = {
        "problem_hook": {
            "hook": f"Bạn muốn dùng {product.name} tiện hơn mỗi ngày?",
            "voiceover": [
                f"Nếu bạn đang tìm một lựa chọn dễ dùng cho nhu cầu hằng ngày, {product.name} đáng để xem.",
                f"Sản phẩm có {feature}, phù hợp khi bạn cần trải nghiệm gọn gàng hơn.",
                f"Bạn có thể xem chi tiết để chọn phiên bản phù hợp với nhu cầu của mình.",
            ],
            "caption": f"Một lựa chọn đáng cân nhắc cho nhu cầu hằng ngày với {product.name}.",
            "hashtags": ["#giaiphap", *common_hashtags],
        },
        "reviewer_natural": {
            "hook": f"Mình thấy {product.name} khá tiện khi dùng thực tế.",
            "voiceover": [
                f"Điểm mình chú ý đầu tiên là {feature}, nhìn khá dễ dùng.",
                f"Các thông tin chính như {second_feature} được trình bày rõ, phù hợp để cân nhắc trước khi mua.",
                "Bạn có thể xem thêm thông tin sản phẩm để chọn đúng nhu cầu.",
            ],
            "caption": f"Review nhanh {product.name} theo góc nhìn sử dụng thực tế.",
            "hashtags": ["#reviewthat", *common_hashtags],
        },
        "benefit_first": {
            "hook": f"Một lựa chọn gọn gàng cho nhu cầu sử dụng hằng ngày.",
            "voiceover": [
                f"{product.name} tập trung vào trải nghiệm tiện hơn trong các tình huống quen thuộc.",
                f"Điểm nổi bật như {feature} giúp sản phẩm dễ phù hợp với nhiều nhu cầu.",
                f"Nếu thấy hợp với cách dùng của bạn, hãy xem chi tiết sản phẩm trước khi chọn mua.",
            ],
            "caption": f"Lợi ích chính của {product.name} trong một video ngắn.",
            "hashtags": ["#loiich", *common_hashtags],
        },
        "use_case_scene": {
            "hook": f"Một tình huống dùng {product.name} khá dễ hình dung.",
            "voiceover": [
                f"Khi cần một sản phẩm gọn và dễ dùng, {product.name} là lựa chọn có thể cân nhắc.",
                f"Những điểm như {feature} và {second_feature} giúp sản phẩm hợp nhiều không gian sử dụng.",
                f"Xem chi tiết để biết sản phẩm có phù hợp với nhu cầu của bạn không.",
            ],
            "caption": f"Một ngữ cảnh sử dụng thực tế cho {product.name}.",
            "hashtags": ["#tinhhuong", *common_hashtags],
        },
        "fast_sales": {
            "hook": f"Gọn nhưng vẫn có nhiều điểm đáng xem.",
            "voiceover": [
                f"{product.name} có thiết kế dễ tiếp cận và thông tin sản phẩm rõ ràng.",
                f"Điểm nổi bật là {feature}, phù hợp nếu bạn muốn chọn nhanh một sản phẩm tiện dụng.",
                product.cta,
            ],
            "caption": f"Xem nhanh những điểm đáng chú ý của {product.name}.",
            "hashtags": ["#deal", "#xemngay", *common_hashtags],
        },
        "comparison_soft": {
            "hook": f"Không phải lúc nào cũng cần chọn phương án cồng kềnh hơn.",
            "voiceover": [
                f"Nếu bạn cần một lựa chọn gọn hơn, {product.name} có vài điểm đáng để cân nhắc.",
                f"Sản phẩm có {feature}, nhưng bạn vẫn nên xem kỹ thông tin shop cung cấp.",
                f"So sánh với nhu cầu thực tế của bạn rồi hãy chọn phiên bản phù hợp.",
            ],
            "caption": f"So sánh nhẹ để cân nhắc {product.name} trước khi mua.",
            "hashtags": ["#tuvan", "#sosanh", *common_hashtags],
        },
    }
    selected = payloads.get(style.id, payloads["reviewer_natural"])
    voiceover = selected["voiceover"]
    return {
        "hook": selected["hook"],
        "voiceover": [{"time_hint": "", "text": text} for text in voiceover],
        "subtitles": [{"start_hint": None, "end_hint": None, "text": text} for text in voiceover],
        "cta": product.cta,
        "caption": selected["caption"],
        "hashtags": selected["hashtags"][:6],
    }


def _find_placeholders(value: Any) -> list[str]:
    found: set[str] = set()

    def walk(item: Any) -> None:
        if isinstance(item, str):
            found.update(PLACEHOLDER_PATTERN.findall(item))
        elif isinstance(item, list):
            for child in item:
                walk(child)
        elif isinstance(item, dict):
            for child in item.values():
                walk(child)

    walk(value)
    return sorted(found)
