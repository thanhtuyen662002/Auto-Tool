from __future__ import annotations

from pathlib import Path

from PIL import Image


SUPPORTED_CUSTOM_OVERLAY_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def select_custom_overlay_asset(path: str | None) -> str:
    if not path:
        raise FileNotFoundError("Bạn đã chọn custom overlay nhưng chưa nhập đường dẫn ảnh/thư mục overlay.")

    source = Path(path).expanduser()
    if source.is_file() and source.suffix.lower() in SUPPORTED_CUSTOM_OVERLAY_EXTENSIONS:
        return str(source)

    if source.is_dir():
        candidates = sorted(
            item
            for item in source.iterdir()
            if item.is_file() and item.suffix.lower() in SUPPORTED_CUSTOM_OVERLAY_EXTENSIONS
        )
        if candidates:
            return str(candidates[0])

    raise FileNotFoundError(
        f"Không tìm thấy ảnh overlay hợp lệ (.png, .jpg, .jpeg, .webp) tại: {path}"
    )


def build_custom_overlay_asset(
    source_path: str | None,
    output_path: str,
    width: int,
    height: int,
    *,
    height_percent: int | None = 100,
    fit_mode: str = "cover",
) -> str:
    if not source_path:
        raise FileNotFoundError("Bạn đã chọn custom overlay nhưng chưa nhập đường dẫn ảnh/thư mục overlay.")

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    source = Image.open(source_path).convert("RGBA")

    normalized_height_percent = _normalize_height_percent(height_percent)
    full_frame = normalized_height_percent >= 100
    if not full_frame:
        alpha_bbox = source.getchannel("A").getbbox()
        if alpha_bbox:
            source = source.crop(alpha_bbox)

    target_height = height if full_frame else max(1, round(height * normalized_height_percent / 100))
    overlay_region = fit_overlay_region(source, width, target_height, fit_mode)

    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.alpha_composite(overlay_region, (0, 0 if full_frame else height - target_height))
    canvas.save(target)
    return str(target)


def fit_overlay_region(source: Image.Image, target_width: int, target_height: int, fit_mode: str) -> Image.Image:
    normalized_fit_mode = (fit_mode or "cover").strip().lower().replace("-", "_")
    if normalized_fit_mode == "stretch":
        return source.resize((target_width, target_height), Image.Resampling.LANCZOS)

    ratio = (
        max(target_width / source.width, target_height / source.height)
        if normalized_fit_mode == "cover"
        else min(target_width / source.width, target_height / source.height)
    )
    resized_width = max(1, round(source.width * ratio))
    resized_height = max(1, round(source.height * ratio))
    resized = source.resize((resized_width, resized_height), Image.Resampling.LANCZOS)

    if normalized_fit_mode == "cover":
        left = max(0, (resized_width - target_width) // 2)
        top = max(0, (resized_height - target_height) // 2)
        return resized.crop((left, top, left + target_width, top + target_height))

    region = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
    region.alpha_composite(
        resized,
        (
            max(0, (target_width - resized_width) // 2),
            max(0, (target_height - resized_height) // 2),
        ),
    )
    return region


def _normalize_height_percent(value: int | None) -> int:
    if value is None:
        value = 100
    return max(5, min(100, int(value)))
