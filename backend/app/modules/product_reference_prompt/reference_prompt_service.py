from __future__ import annotations

from pathlib import Path

from app.modules.product_reference_prompt.prompt_exporter import PromptExporter
from app.modules.product_reference_prompt.reference_schema import ProductReferenceSummary, ProductStoryboard, VideoPromptPack
from app.modules.product_reference_prompt.reference_summary_builder import ProductReferenceSummaryBuilder, _load_project_config
from app.modules.product_reference_prompt.storyboard_generator import ProductStoryboardGenerator
from app.modules.product_reference_prompt.video_prompt_generator import ProductVideoPromptGenerator


class ProductReferencePromptService:
    def __init__(
        self,
        summary_builder: ProductReferenceSummaryBuilder | None = None,
        storyboard_generator: ProductStoryboardGenerator | None = None,
        video_prompt_generator: ProductVideoPromptGenerator | None = None,
        exporter: PromptExporter | None = None,
    ) -> None:
        self.summary_builder = summary_builder or ProductReferenceSummaryBuilder()
        self.storyboard_generator = storyboard_generator or ProductStoryboardGenerator(self.summary_builder)
        self.video_prompt_generator = video_prompt_generator or ProductVideoPromptGenerator(
            self.summary_builder,
            self.storyboard_generator,
        )
        self.exporter = exporter or PromptExporter()

    def generate_reference_summary(self, project_id: str) -> ProductReferenceSummary:
        return self.summary_builder.build_summary(project_id)

    def generate_storyboard(
        self,
        project_id: str,
        duration_seconds: float = 8,
        scene_count: int = 5,
        style: str | None = None,
    ) -> ProductStoryboard:
        return self.storyboard_generator.generate_storyboard(
            project_id=project_id,
            duration_seconds=duration_seconds,
            scene_count=scene_count,
            style=style,
        )

    def generate_video_prompt_pack(
        self,
        project_id: str,
        duration_seconds: float = 8,
        scene_count: int = 5,
        model_hint: str | None = None,
        style: str | None = None,
        export_files: bool = True,
    ) -> tuple[VideoPromptPack, dict[str, str]]:
        prompt_pack = self.video_prompt_generator.generate_video_prompt_pack(
            project_id=project_id,
            duration_seconds=duration_seconds,
            scene_count=scene_count,
            model_hint=model_hint,
            style=style,
        )
        files = self.exporter.export_prompt_pack(prompt_pack, str(self.output_dir_for_project(project_id))) if export_files else {}
        return prompt_pack, files

    def output_dir_for_project(self, project_id: str) -> Path:
        config = _load_project_config(project_id)
        return Path(config.output_folder) / config.project_name / "prompt_pack"
