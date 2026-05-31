from __future__ import annotations

from copy import deepcopy

from app.modules.timeline_templates.template_schema import TimelineSlot, TimelineTemplate


DEFAULT_TEMPLATE_ID = "ugc_reviewer_natural"

PRESET_TEMPLATE_MAP: dict[str, str] = {
    "Light Recut": "product_showcase_clean",
    "Balanced Recut": "ugc_reviewer_natural",
    "Aggressive Remix": "fast_tiktok_recut",
}


def list_timeline_templates() -> list[TimelineTemplate]:
    return [template.model_copy(deep=True) for template in _TEMPLATES]


def get_timeline_template(template_id: str | None) -> TimelineTemplate:
    requested_id = (template_id or DEFAULT_TEMPLATE_ID).strip() or DEFAULT_TEMPLATE_ID
    for template in _TEMPLATES:
        if template.id == requested_id:
            return template.model_copy(deep=True)

    default_template = next(template for template in _TEMPLATES if template.id == DEFAULT_TEMPLATE_ID)
    return default_template.model_copy(deep=True)


def template_id_for_preset(preset_name: str) -> str:
    return PRESET_TEMPLATE_MAP.get(preset_name, DEFAULT_TEMPLATE_ID)


def _slot(
    name: str,
    start_ratio: float,
    end_ratio: float,
    preferred_tags: list[str],
    text_role: str,
    energy_level: str = "medium",
    avoided_tags: list[str] | None = None,
) -> TimelineSlot:
    return TimelineSlot(
        name=name,
        start_ratio=start_ratio,
        end_ratio=end_ratio,
        preferred_tags=preferred_tags,
        avoided_tags=deepcopy(avoided_tags or []),
        min_clip_duration=0.8,
        max_clip_duration=3.0,
        energy_level=energy_level,
        text_role=text_role,
    )


_TEMPLATES: list[TimelineTemplate] = [
    TimelineTemplate(
        id="product_showcase_clean",
        name="Product Showcase Clean",
        description="Clean product showcase with clear product shots, demo, benefit, and CTA.",
        supported_durations=[8, 12, 15, 30, 45, 60],
        slots=[
            _slot("hook", 0.0, 0.15, ["high_motion", "sharp", "bright"], "hook", "high"),
            _slot("product", 0.15, 0.45, ["sharp", "stable", "bright"], "product", "medium"),
            _slot("demo", 0.45, 0.75, ["high_motion", "stable"], "demo", "medium"),
            _slot("benefit", 0.75, 0.90, ["stable", "bright"], "benefit", "low"),
            _slot("cta", 0.90, 1.0, ["stable", "sharp"], "cta", "low"),
        ],
    ),
    TimelineTemplate(
        id="ugc_reviewer_natural",
        name="UGC Reviewer Natural",
        description="Natural review pacing for consumer products with situation, product, use case, benefit, and CTA.",
        supported_durations=[8, 12, 15, 30, 45, 60],
        slots=[
            _slot("hook", 0.0, 0.20, ["high_motion", "bright"], "hook", "high"),
            _slot("product", 0.20, 0.45, ["stable", "sharp"], "product", "medium"),
            _slot("demo", 0.45, 0.70, ["high_motion"], "demo", "medium"),
            _slot("benefit", 0.70, 0.88, ["stable"], "benefit", "low"),
            _slot("cta", 0.88, 1.0, ["stable", "bright"], "cta", "low"),
        ],
    ),
    TimelineTemplate(
        id="fast_tiktok_recut",
        name="Fast TikTok Recut",
        description="Fast-paced short-form recut with quick hooks, montage-style demo, and compact CTA.",
        supported_durations=[8, 12, 15, 30],
        slots=[
            _slot("hook", 0.0, 0.12, ["high_motion", "sharp"], "hook", "high"),
            _slot("product", 0.12, 0.35, ["sharp", "bright"], "product", "high"),
            _slot("demo", 0.35, 0.70, ["high_motion"], "demo", "high"),
            _slot("benefit", 0.70, 0.88, ["high_motion", "stable"], "benefit", "medium"),
            _slot("cta", 0.88, 1.0, ["stable"], "cta", "medium"),
        ],
    ),
    TimelineTemplate(
        id="problem_solution",
        name="Problem Solution",
        description="Problem to solution structure for product videos that need a clear narrative arc.",
        supported_durations=[12, 15, 30, 45, 60],
        slots=[
            _slot("hook", 0.0, 0.25, ["high_motion", "low_motion"], "hook", "medium"),
            _slot("product", 0.25, 0.50, ["sharp", "stable"], "product", "medium"),
            _slot("demo", 0.50, 0.78, ["high_motion", "stable"], "demo", "medium"),
            _slot("benefit", 0.78, 0.90, ["bright", "stable"], "benefit", "low"),
            _slot("cta", 0.90, 1.0, ["stable", "sharp"], "cta", "low"),
        ],
    ),
]
