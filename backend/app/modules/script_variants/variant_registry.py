from __future__ import annotations

from app.modules.script_variants.variant_schema import ScriptVariantStyle


_STYLES: list[ScriptVariantStyle] = [
    ScriptVariantStyle(
        id="problem_hook",
        name="Problem Hook",
        description="Hook dạng nêu vấn đề, gần gũi và dẫn vào giải pháp sản phẩm.",
        hook_type="Nêu một vấn đề hoặc nhu cầu thường gặp của người mua.",
        tone="Gần gũi, dễ hiểu, không tạo cảm giác ép mua.",
        cta_style="Mềm, gợi ý xem thêm thông tin.",
        best_for_templates=["problem_solution", "ugc_reviewer_natural"],
    ),
    ScriptVariantStyle(
        id="reviewer_natural",
        name="Reviewer Natural",
        description="Hook như người dùng đang review tự nhiên sau khi trải nghiệm.",
        hook_type="Mở đầu bằng cảm nhận cá nhân tự nhiên.",
        tone="Tự nhiên như người thật, đời thường, không quá quảng cáo.",
        cta_style="Nhẹ nhàng, khuyến khích cân nhắc trước khi chọn mua.",
        best_for_templates=["ugc_reviewer_natural"],
    ),
    ScriptVariantStyle(
        id="benefit_first",
        name="Benefit First",
        description="Đi thẳng vào lợi ích chính và giữ giọng bán hàng vừa phải.",
        hook_type="Nêu lợi ích chính ngay đầu video.",
        tone="Rõ ràng, gọn, bán hàng vừa phải.",
        cta_style="Trung bình, rõ hành động nhưng không spam.",
        best_for_templates=["product_showcase_clean"],
    ),
    ScriptVariantStyle(
        id="use_case_scene",
        name="Use Case Scene",
        description="Mở đầu bằng tình huống sử dụng cụ thể trong đời sống.",
        hook_type="Mô tả một ngữ cảnh sử dụng thực tế.",
        tone="Đời thường, dễ hình dung.",
        cta_style="Mềm, dẫn người xem xem chi tiết.",
        best_for_templates=["ugc_reviewer_natural", "product_showcase_clean"],
    ),
    ScriptVariantStyle(
        id="fast_sales",
        name="Fast Sales",
        description="Hook ngắn, nhanh, phù hợp video TikTok/Reels nhịp mạnh.",
        hook_type="Hook ngắn, nhanh, tạo chú ý trong 1-2 giây đầu.",
        tone="Nhanh, dứt khoát, năng lượng cao.",
        cta_style="Mạnh hơn nhưng vẫn không phóng đại.",
        best_for_templates=["fast_tiktok_recut"],
    ),
    ScriptVariantStyle(
        id="comparison_soft",
        name="Soft Comparison",
        description="So sánh nhẹ nhàng, tư vấn lựa chọn mà không công kích.",
        hook_type="So sánh nhẹ với lựa chọn quen thuộc hoặc nhu cầu thay thế.",
        tone="Tư vấn, khách quan, không hạ thấp sản phẩm khác.",
        cta_style="Trung bình, khuyến khích xem kỹ thông tin.",
        best_for_templates=["problem_solution"],
    ),
]


def list_variant_styles() -> list[ScriptVariantStyle]:
    return [style.model_copy(deep=True) for style in _STYLES]


def get_variant_style(style_id: str) -> ScriptVariantStyle:
    for style in _STYLES:
        if style.id == style_id:
            return style.model_copy(deep=True)
    raise ValueError(f"Unknown script variant style: {style_id}")


class VariantPlanner:
    def plan_variants(
        self,
        output_count: int,
        timeline_template_id: str | None,
        preferred_variant_ids: list[str] | None = None,
    ) -> list[ScriptVariantStyle]:
        if output_count <= 0:
            raise ValueError("output_count must be greater than 0.")

        styles = list_variant_styles()
        ordered = self._ordered_for_template(styles, timeline_template_id, preferred_variant_ids)
        planned: list[ScriptVariantStyle] = []

        for index in range(output_count):
            if index < len(ordered):
                candidate = ordered[index]
            else:
                candidate = ordered[index % len(ordered)]

            if planned and candidate.id == planned[-1].id and len(ordered) > 1:
                candidate = ordered[(index + 1) % len(ordered)]
            planned.append(candidate)

        return planned

    @staticmethod
    def _ordered_for_template(
        styles: list[ScriptVariantStyle],
        timeline_template_id: str | None,
        preferred_variant_ids: list[str] | None = None,
    ) -> list[ScriptVariantStyle]:
        preferred_ids = preferred_variant_ids or []
        by_id = {style.id: style for style in styles}
        industry_preferred = [by_id[style_id] for style_id in preferred_ids if style_id in by_id]

        if not timeline_template_id:
            others = [style for style in styles if style not in industry_preferred]
            return industry_preferred + others

        template_preferred = [style for style in styles if timeline_template_id in style.best_for_templates]
        ordered: list[ScriptVariantStyle] = []
        for style in [*industry_preferred, *template_preferred, *styles]:
            if style not in ordered:
                ordered.append(style)
        return ordered
