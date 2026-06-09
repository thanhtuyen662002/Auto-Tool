from __future__ import annotations

from datetime import datetime

from app.modules.product_reference_prompt.reference_schema import ProductReferenceSummary, ProductStoryboard, VideoPromptPack
from app.modules.product_reference_prompt.reference_summary_builder import ProductReferenceSummaryBuilder
from app.modules.product_reference_prompt.storyboard_generator import ProductStoryboardGenerator


class ProductVideoPromptGenerator:
    def __init__(
        self,
        summary_builder: ProductReferenceSummaryBuilder | None = None,
        storyboard_generator: ProductStoryboardGenerator | None = None,
    ) -> None:
        self.summary_builder = summary_builder or ProductReferenceSummaryBuilder()
        self.storyboard_generator = storyboard_generator or ProductStoryboardGenerator(self.summary_builder)

    def generate_video_prompt_pack(
        self,
        project_id: str,
        duration_seconds: float = 8,
        scene_count: int = 5,
        model_hint: str | None = None,
        style: str | None = None,
    ) -> VideoPromptPack:
        summary = self.summary_builder.build_summary(project_id)
        storyboard = self.storyboard_generator.generate_storyboard(
            project_id=project_id,
            duration_seconds=duration_seconds,
            scene_count=scene_count,
            style=style,
        )
        negative_prompt = _negative_prompt_text(storyboard)
        return VideoPromptPack(
            project_id=project_id,
            product_name=summary.product_name,
            prompt_type=style or "product_showcase",
            model_hint=_clean_model_hint(model_hint),
            product_reference_summary=summary,
            storyboard=storyboard,
            video_prompt=_full_prompt(summary, storyboard, model_hint),
            negative_prompt=negative_prompt,
            short_prompt=_short_prompt(summary, storyboard, model_hint),
            json_prompt=_json_prompt(summary, storyboard, model_hint),
            created_at=datetime.now().replace(microsecond=0).isoformat(),
        )


def _full_prompt(
    summary: ProductReferenceSummary,
    storyboard: ProductStoryboard,
    model_hint: str | None,
) -> str:
    lines: list[str] = [
        f"Create a vertical 9:16 product showcase video for {summary.product_name}.",
    ]
    if model_hint:
        lines.append(f"Model hint: {model_hint}. Keep the prompt generic enough for other video models.")
    lines.extend(
        [
            "",
            "PRODUCT REFERENCE:",
            "Use the selected product reference images as the main source of truth.",
            f"Product name: {summary.product_name}",
            f"Brand: {summary.brand or 'not provided'}",
            f"Reference assets: {len(summary.reference_assets)}",
            f"Main product asset id: {summary.main_product_asset_id or 'not selected'}",
            "",
            "PRODUCT ACCURACY LOCK:",
            *_bullet_lines(summary.product_accuracy_lock),
            "",
            "ALLOWED CLAIMS:",
            *(_bullet_lines(summary.allowed_claims) if summary.allowed_claims else ["- Use only claims explicitly provided in product info."]),
            "",
            "VIDEO STYLE:",
            f"- {summary.visual_identity}",
            "- Clean vertical product video, natural motion, realistic lighting.",
            "- Leave room for subtitle/caption added later by Auto Tool.",
            "",
            "SCENE STRUCTURE:",
        ]
    )
    for scene in storyboard.scenes:
        lines.extend(
            [
                f"Scene {scene.scene_index} ({scene.duration_seconds}s) - {scene.purpose}:",
                f"- Visual: {scene.visual_description}",
                f"- Camera: {scene.camera_direction}",
                *[f"- Accuracy: {note}" for note in scene.product_accuracy_notes],
            ]
        )

    lines.extend(
        [
            "",
            "CAMERA:",
            "- Vertical 9:16 framing.",
            "- Keep the product visible, sharp, and not cropped awkwardly.",
            "- Use simple pans, push-ins, close-ups, and stable product shots.",
            "",
            "LIGHTING:",
            "- Realistic product lighting.",
            "- Avoid overexposure and heavy color shifts that change the product color.",
            "",
            "TEXT:",
            "- No generated text on screen unless explicitly requested.",
            "- Subtitle/caption will be added in post-production by Auto Tool.",
            "",
            "NEGATIVE PROMPT:",
            *_bullet_lines(storyboard.negative_prompt),
            "",
            "FORBIDDEN CLAIMS:",
            *_bullet_lines(summary.forbidden_claims),
        ]
    )
    return "\n".join(lines)


def _short_prompt(
    summary: ProductReferenceSummary,
    storyboard: ProductStoryboard,
    model_hint: str | None,
) -> str:
    scene_summary = "; ".join(f"{scene.scene_index}. {scene.purpose}" for scene in storyboard.scenes)
    hint = f" for {model_hint}" if model_hint else ""
    return (
        f"Vertical 9:16 realistic product showcase{hint} for {summary.product_name}. "
        "Use selected reference images as the source of truth. "
        f"Scenes: {scene_summary}. "
        "Keep product model, color, logo, packaging, and physical details accurate. "
        "No generated text, no watermark, no fake claims."
    )


def _json_prompt(
    summary: ProductReferenceSummary,
    storyboard: ProductStoryboard,
    model_hint: str | None,
) -> dict:
    return {
        "aspect_ratio": storyboard.aspect_ratio,
        "duration_seconds": storyboard.total_duration_seconds,
        "model_hint": _clean_model_hint(model_hint),
        "product": {
            "name": summary.product_name,
            "brand": summary.brand,
            "accuracy_lock": summary.product_accuracy_lock,
            "allowed_claims": summary.allowed_claims,
            "forbidden_claims": summary.forbidden_claims,
        },
        "reference_assets": [
            {
                "asset_id": asset.asset_id,
                "role": asset.role,
                "local_path": asset.local_path,
                "original_url": asset.original_url,
            }
            for asset in summary.reference_assets
        ],
        "scenes": [
            {
                "scene": scene.scene_index,
                "duration": scene.duration_seconds,
                "purpose": scene.purpose,
                "visual": scene.visual_description,
                "camera": scene.camera_direction,
                "accuracy_notes": scene.product_accuracy_notes,
            }
            for scene in storyboard.scenes
        ],
        "negative_prompt": storyboard.negative_prompt,
    }


def _negative_prompt_text(storyboard: ProductStoryboard) -> str:
    return "\n".join(storyboard.negative_prompt)


def _bullet_lines(values: list[str]) -> list[str]:
    return [f"- {value}" for value in values]


def _clean_model_hint(value: str | None) -> str | None:
    cleaned = " ".join(str(value or "").strip().split())
    if not cleaned or cleaned.lower() == "generic":
        return None
    return cleaned
