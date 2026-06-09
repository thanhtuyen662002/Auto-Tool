from __future__ import annotations

from app.modules.product_reference_prompt.reference_schema import ProductStoryboard, StoryboardScene
from app.modules.product_reference_prompt.reference_summary_builder import ProductReferenceSummaryBuilder


DEFAULT_NEGATIVE_PROMPT = [
    "wrong product model",
    "extra parts",
    "changed color",
    "changed logo",
    "extra text",
    "watermark",
    "random UI text",
    "distorted product",
    "duplicate product",
    "unreadable text",
    "fake claims",
    "hands covering product",
    "low quality",
    "blurry",
    "overexposed",
]

INDUSTRY_NEGATIVE_PROMPTS: dict[str, list[str]] = {
    "tech_electronics": ["extra lens", "extra antenna", "wrong ports", "wrong screen UI"],
    "fashion_accessories": ["wrong clothing shape", "changed color", "wrong logo placement", "extra patterns"],
    "beauty_cosmetics": ["changed packaging", "wrong label", "fake medical claim text"],
}


class ProductStoryboardGenerator:
    def __init__(self, summary_builder: ProductReferenceSummaryBuilder | None = None) -> None:
        self.summary_builder = summary_builder or ProductReferenceSummaryBuilder()

    def generate_storyboard(
        self,
        project_id: str,
        duration_seconds: float = 8,
        scene_count: int = 5,
        style: str | None = None,
    ) -> ProductStoryboard:
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be greater than 0.")
        if scene_count <= 0:
            raise ValueError("scene_count must be greater than 0.")

        summary = self.summary_builder.build_summary(project_id)
        industry_id = summary.industry_preset_id or "general_product"
        durations = _scene_durations(duration_seconds, scene_count)
        templates = _scene_templates(industry_id, style)
        scenes: list[StoryboardScene] = []
        for index in range(scene_count):
            template = templates[index] if index < len(templates) else _extra_scene_template(index + 1)
            scenes.append(
                StoryboardScene(
                    scene_index=index + 1,
                    duration_seconds=durations[index],
                    scene_type=template["scene_type"],
                    purpose=template["purpose"],
                    visual_description=template["visual"].format(product=summary.product_name),
                    camera_direction=template["camera"],
                    product_accuracy_notes=_accuracy_notes_for_scene(summary.product_accuracy_lock, index),
                    subtitle_suggestion=template["subtitle"].format(product=summary.product_name),
                    voiceover_suggestion=template["voiceover"].format(product=summary.product_name),
                )
            )

        return ProductStoryboard(
            project_id=project_id,
            title=f"Storyboard {scene_count} cảnh cho {summary.product_name}",
            total_duration_seconds=round(duration_seconds, 2),
            aspect_ratio="9:16",
            scenes=scenes,
            negative_prompt=negative_prompt_for_industry(industry_id),
            reference_assets=summary.reference_assets,
        )


def negative_prompt_for_industry(industry_id: str | None) -> list[str]:
    result = [*DEFAULT_NEGATIVE_PROMPT]
    result.extend(INDUSTRY_NEGATIVE_PROMPTS.get(industry_id or "", []))
    seen: set[str] = set()
    cleaned: list[str] = []
    for item in result:
        if item in seen:
            continue
        cleaned.append(item)
        seen.add(item)
    return cleaned


def _scene_durations(total_duration: float, scene_count: int) -> list[float]:
    if scene_count == 5 and total_duration <= 8.5:
        weights = [1.5, 1.5, 2.0, 2.0, 1.0]
    elif scene_count == 5 and total_duration >= 9.5:
        weights = [1, 1, 1, 1, 1]
    else:
        weights = [1 for _ in range(scene_count)]

    total_weight = sum(weights)
    durations = [round(total_duration * weight / total_weight, 2) for weight in weights[:scene_count]]
    if len(durations) < scene_count:
        durations.extend([round(total_duration / scene_count, 2)] * (scene_count - len(durations)))
    durations[-1] = round(total_duration - sum(durations[:-1]), 2)
    return durations


def _scene_templates(industry_id: str, style: str | None) -> list[dict[str, str]]:
    if style == "problem_solution" or industry_id == "home_lifestyle":
        return [
            _template("hook_visual", "problem hook", "Mở đầu bằng bối cảnh vấn đề thường gặp, sản phẩm {product} chưa xuất hiện quá sớm.", "Handheld nhẹ, cắt nhanh vào vấn đề.", "Có vấn đề này thì xem thử", "Một tình huống quen thuộc trước khi dùng sản phẩm."),
            _template("product_hero", "solution reveal", "Sản phẩm {product} xuất hiện rõ ở trung tâm khung hình.", "Push-in chậm, giữ sản phẩm nét.", "{product} là giải pháp gọn gàng", "Đây là sản phẩm được dùng để xử lý nhu cầu đó."),
            _template("feature_demo", "demo", "Minh họa một tính năng đã được cung cấp, không thêm tính năng mới.", "Close-up thao tác hoặc chi tiết sản phẩm.", "Demo nhanh tính năng chính", "Tập trung vào tính năng đã có trong thông tin sản phẩm."),
            _template("use_case", "benefit", "Đặt sản phẩm trong không gian sử dụng thực tế, sạch và dễ hiểu.", "Wide shot dọc, chuyển động nhẹ.", "Dùng thực tế trong nhà", "Cho thấy sản phẩm phù hợp với ngữ cảnh sử dụng hằng ngày."),
            _template("cta", "cta", "Final product shot với bố cục rõ, chừa khoảng trống cho subtitle hậu kỳ.", "Static hero shot, ánh sáng đều.", "Xem chi tiết sản phẩm", "Kết thúc bằng lời nhắc xem chi tiết."),
        ]
    if industry_id == "tech_electronics":
        return [
            _template("hook_visual", "modern setup hook", "Cảnh setup hiện đại, ánh sáng sạch, sản phẩm {product} là điểm nhấn.", "Tilt hoặc slide nhẹ qua không gian setup.", "Setup gọn mà nhìn rất ổn", "Mở bằng bối cảnh công nghệ hiện đại."),
            _template("product_hero", "hero close-up", "Close-up sản phẩm {product}, giữ đúng model, màu sắc và chi tiết theo ảnh tham chiếu.", "Slow push-in vào mặt trước sản phẩm.", "Cận cảnh sản phẩm", "Cho người xem thấy rõ sản phẩm chính."),
            _template("feature_demo", "feature demo", "Demo tính năng đã được cung cấp, tránh hiển thị UI hoặc thông số chưa có.", "Cut-in chi tiết, camera ổn định.", "Tính năng đáng chú ý", "Nêu một điểm nổi bật có trong dữ liệu."),
            _template("use_case", "use case", "Sản phẩm trong phòng khách hoặc góc làm việc, bối cảnh thực tế.", "Wide shot dọc, chuyển động chậm.", "Dùng trong nhiều không gian", "Gợi tình huống sử dụng thực tế."),
            _template("cta", "final product shot", "Sản phẩm ở trung tâm, nền sạch, không tạo chữ trong video.", "Static shot, ánh sáng cân bằng.", "Xem chi tiết ngay", "Kết thúc bằng CTA rõ."),
        ]
    if industry_id == "beauty_cosmetics":
        return [
            _template("hook_visual", "beauty routine hook", "Routine làm đẹp nhẹ nhàng, sản phẩm {product} nằm trong khung sạch.", "Soft handheld, ánh sáng mềm.", "Routine gọn hơn mỗi ngày", "Mở bằng cảm giác gần gũi."),
            _template("product_hero", "packaging hero", "Hero shot sản phẩm {product}, giữ đúng bao bì và nhãn theo ảnh tham chiếu.", "Slow push-in, nền tối giản.", "Nhìn rõ sản phẩm", "Cho thấy bao bì chính xác."),
            _template("feature_demo", "usage detail", "Minh họa texture hoặc cách dùng nếu dữ liệu cho phép, không thêm claim điều trị.", "Macro/close-up sạch.", "Dễ dùng trong routine", "Tập trung vào trải nghiệm sử dụng."),
            _template("use_case", "vanity use case", "Sản phẩm trên bàn trang điểm hoặc không gian chăm sóc cá nhân.", "Pan nhẹ theo chiều dọc.", "Phù hợp dùng hằng ngày", "Đưa sản phẩm vào bối cảnh thực tế."),
            _template("cta", "soft CTA", "Final product shot mềm mại, chừa khoảng trống cho subtitle.", "Static shot, ánh sáng đều.", "Xem chi tiết sản phẩm", "CTA rõ nhưng không phóng đại."),
        ]
    if industry_id == "fashion_accessories":
        return [
            _template("hook_visual", "outfit hook", "Outfit hoặc lifestyle scene, sản phẩm {product} xuất hiện tự nhiên.", "Handheld nhẹ, chuyển động theo người mẫu hoặc flat lay.", "Phối đồ nhìn gọn hơn", "Mở bằng tình huống thời trang."),
            _template("product_hero", "shape hero", "Hiển thị rõ form dáng, màu sắc và chi tiết sản phẩm {product}.", "Full-frame product shot, giữ dọc 9:16.", "Rõ form dáng và màu", "Cho thấy hình dáng thật của sản phẩm."),
            _template("feature_demo", "material detail", "Cận chất liệu hoặc chi tiết đã được cung cấp trong specs/features.", "Close-up chi tiết, không đổi họa tiết.", "Chi tiết đáng chú ý", "Nhấn vào chi tiết được cung cấp."),
            _template("use_case", "wearing use case", "Bối cảnh mặc ngoài trời, đi làm hoặc sinh hoạt phù hợp sản phẩm.", "Wide shot, camera ổn định.", "Dễ dùng trong nhiều dịp", "Gợi cách dùng thực tế."),
            _template("cta", "brand CTA", "Final shot rõ màu/size/brand nếu dữ liệu có, không thêm chữ lên hình.", "Static product shot.", "Xem chi tiết ngay", "Kết thúc gọn."),
        ]
    return [
        _template("hook_visual", "hook visual", "Mở đầu bằng cảnh lifestyle ngắn, sản phẩm {product} là chủ thể chính hoặc sắp xuất hiện.", "Handheld nhẹ, nhịp nhanh vừa phải.", "Sản phẩm này đáng xem", "Mở bằng hook tự nhiên."),
        _template("product_hero", "product hero", "Hero shot rõ sản phẩm {product}, giữ đúng màu sắc và form dáng theo ảnh tham chiếu.", "Slow push-in hoặc slide ngang nhẹ.", "Nhìn rõ sản phẩm", "Cho người xem nhận diện sản phẩm."),
        _template("feature_demo", "feature/demo", "Minh họa một điểm nổi bật đã được cung cấp, không thêm tính năng mới.", "Close-up chi tiết, cắt gọn.", "Điểm nổi bật chính", "Nêu một lợi ích thực tế."),
        _template("use_case", "use case/benefit", "Đưa sản phẩm vào bối cảnh sử dụng thực tế, sạch và dễ hiểu.", "Wide shot dọc, chuyển động chậm.", "Dùng hằng ngày khá tiện", "Gợi nhu cầu sử dụng."),
        _template("cta", "cta/final shot", "Final product shot rõ ràng, không tạo chữ trong video vì Auto Tool sẽ thêm subtitle hậu kỳ.", "Static shot, sản phẩm ở trung tâm.", "Xem chi tiết sản phẩm", "CTA rõ và không spam."),
    ]


def _template(
    scene_type: str,
    purpose: str,
    visual: str,
    camera: str,
    subtitle: str,
    voiceover: str,
) -> dict[str, str]:
    return {
        "scene_type": scene_type,
        "purpose": purpose,
        "visual": visual,
        "camera": camera,
        "subtitle": subtitle,
        "voiceover": voiceover,
    }


def _extra_scene_template(scene_index: int) -> dict[str, str]:
    return _template(
        "detail_scene",
        f"detail {scene_index}",
        "Thêm một góc sản phẩm {product} rõ ràng, không làm sai chi tiết vật lý.",
        "Close-up ổn định, chuyển động nhẹ.",
        "Thêm góc nhìn sản phẩm",
        "Bổ sung một góc nhìn rõ hơn về sản phẩm.",
    )


def _accuracy_notes_for_scene(accuracy_lock: list[str], scene_index: int) -> list[str]:
    base = accuracy_lock[:4]
    if scene_index >= 2:
        base.extend(accuracy_lock[4:7])
    return base
