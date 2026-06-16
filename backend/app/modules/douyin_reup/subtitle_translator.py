from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from app.adapters.gemini_adapter import GeminiAdapter, ScriptGenerationError
from app.modules.douyin_reup.douyin_schema import TranslationResult
from app.modules.douyin_reup.subtitle_timing_guard import SubtitleBlock, parse_srt_blocks, write_srt_blocks
from app.utils.file_utils import ensure_dir


class SubtitleTranslator:
    def translate_srt(
        self,
        source_srt_path: str,
        output_srt_path: str,
        source_language: str = "zh",
        target_language: str = "vi",
        provider: str = "gemini",
        model_name: str = "gemini-3.1-flash-lite",
        api_keys: list[str] | None = None,
    ) -> TranslationResult:
        target = Path(output_srt_path)
        ensure_dir(target.parent)
        warnings: list[str] = []

        if source_language.strip().lower() == target_language.strip().lower():
            shutil.copy2(source_srt_path, target)
            warnings.append("Ngôn ngữ nguồn trùng ngôn ngữ đích nên giữ nguyên subtitle.")
            return TranslationResult(
                source_srt_path=source_srt_path,
                translated_srt_path=str(target),
                provider="copy",
                source_language=source_language,
                target_language=target_language,
                warnings=warnings,
            )

        if provider.strip().lower() != "gemini":
            message = f"Provider dịch subtitle chưa hỗ trợ: {provider}."
            if not _translation_fallback_enabled():
                raise RuntimeError(f"{message} Hãy chọn Gemini hoặc cấu hình provider dịch hợp lệ.")
            shutil.copy2(source_srt_path, target)
            warnings.append(f"{message} Đã giữ nguyên subtitle nguồn vì AUTO_TOOL_ALLOW_TRANSLATION_FALLBACK=1.")
            return self._fallback_result(source_srt_path, str(target), source_language, target_language, warnings)

        blocks = parse_srt_blocks(source_srt_path)
        if not blocks:
            raise RuntimeError(f"File subtitle nguồn không có block SRT hợp lệ: {source_srt_path}")

        try:
            translated_blocks = self._translate_blocks_with_gemini(
                blocks=blocks,
                source_language=source_language,
                target_language=target_language,
                model_name=model_name,
                api_keys=api_keys or [],
            )
            write_srt_blocks(translated_blocks, str(target))
            return TranslationResult(
                source_srt_path=source_srt_path,
                translated_srt_path=str(target),
                provider="gemini",
                source_language=source_language,
                target_language=target_language,
            )
        except Exception as exc:
            if not _translation_fallback_enabled():
                raise RuntimeError(
                    "Dịch subtitle bằng Gemini thất bại nên dừng render để tránh xuất video sai ngôn ngữ. "
                    f"Chi tiết: {exc}"
                ) from exc
            shutil.copy2(source_srt_path, target)
            warnings.append(
                "Dịch subtitle bằng Gemini thất bại, đã giữ nguyên subtitle nguồn vì "
                f"AUTO_TOOL_ALLOW_TRANSLATION_FALLBACK=1: {exc}"
            )
            return self._fallback_result(source_srt_path, str(target), source_language, target_language, warnings)

    def _translate_blocks_with_gemini(
        self,
        blocks: list[SubtitleBlock],
        source_language: str,
        target_language: str,
        model_name: str,
        api_keys: list[str],
    ) -> list[SubtitleBlock]:
        adapter = GeminiAdapter(api_key=None, model_name=model_name, api_keys=api_keys, timeout_seconds=45)
        translated: list[SubtitleBlock] = []

        for chunk in _chunk_blocks(blocks, size=40):
            prompt = build_srt_translation_prompt(
                _blocks_to_srt_text(chunk),
                source_language=source_language,
                target_language=target_language,
            )
            payload = adapter.generate_json(prompt)
            srt_text = str(payload.get("srt") or "").strip()
            if not srt_text:
                raise ScriptGenerationError("Gemini không trả field srt cho chunk subtitle.")
            chunk_blocks = _parse_srt_text_from_response(srt_text)
            if len(chunk_blocks) != len(chunk):
                raise ScriptGenerationError(
                    f"Gemini trả sai số block subtitle: expected={len(chunk)}, actual={len(chunk_blocks)}"
                )
            for original, translated_block in zip(chunk, chunk_blocks):
                translated.append(
                    SubtitleBlock(
                        index=len(translated) + 1,
                        start=original.start,
                        end=original.end,
                        text=translated_block.text,
                    )
                )

        return translated

    @staticmethod
    def _fallback_result(
        source_srt_path: str,
        output_srt_path: str,
        source_language: str,
        target_language: str,
        warnings: list[str],
    ) -> TranslationResult:
        return TranslationResult(
            source_srt_path=source_srt_path,
            translated_srt_path=output_srt_path,
            provider="fallback_source_text",
            source_language=source_language,
            target_language=target_language,
            warnings=warnings,
        )


def build_srt_translation_prompt(
    srt_chunk: str,
    source_language: str = "zh",
    target_language: str = "vi",
) -> str:
    return f"""
Bạn là chuyên gia dịch subtitle video ngắn từ {source_language} sang {target_language}.

Yêu cầu bắt buộc:
- Chỉ dịch phần text subtitle, giữ nguyên thứ tự block.
- Không đổi timestamp.
- Không bỏ sót block, không rút gọn ý, không tóm tắt.
- Không thêm giải thích, markdown hoặc ghi chú.
- Câu tiếng Việt tự nhiên, ngắn, dễ đọc trên màn hình dọc.
- Mỗi block nên là một ý hoàn chỉnh, không tách câu vô lý.
- Trả về JSON hợp lệ duy nhất theo schema: {{"srt": "nội dung SRT đã dịch"}}

SRT cần dịch:
{srt_chunk}
""".strip()


def _chunk_blocks(blocks: list[SubtitleBlock], size: int) -> list[list[SubtitleBlock]]:
    return [blocks[index : index + size] for index in range(0, len(blocks), size)]


def _blocks_to_srt_text(blocks: list[SubtitleBlock]) -> str:
    parts: list[str] = []
    for index, block in enumerate(blocks, start=1):
        parts.append(
            "\n".join(
                [
                    str(index),
                    f"{_format_for_prompt(block.start)} --> {_format_for_prompt(block.end)}",
                    block.text.strip(),
                ]
            )
        )
    return "\n\n".join(parts)


def _parse_srt_text_from_response(text: str) -> list[SubtitleBlock]:
    handle = tempfile.NamedTemporaryFile("w", suffix=".srt", delete=False, encoding="utf-8")
    temp_path = Path(handle.name)
    try:
        with handle:
            handle.write(text)
        return parse_srt_blocks(str(temp_path))
    finally:
        temp_path.unlink(missing_ok=True)


def _format_for_prompt(seconds: float) -> str:
    from app.modules.douyin_reup.subtitle_timing_guard import format_srt_timestamp

    return format_srt_timestamp(seconds)


def _translation_fallback_enabled() -> bool:
    return os.getenv("AUTO_TOOL_ALLOW_TRANSLATION_FALLBACK", "0").strip().lower() in {"1", "true", "yes", "on"}
