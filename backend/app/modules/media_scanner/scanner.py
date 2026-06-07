from __future__ import annotations

from pathlib import Path

from app.adapters.ffmpeg_adapter import FFmpegError, MissingFFmpegError, probe_video
from app.modules.cache.cache_service import CacheService
from app.schemas.media_schema import MediaFile
from app.utils.logger import get_logger


logger = get_logger(__name__)


class MediaScanner:
    supported_extensions = {".mp4", ".mov", ".mkv", ".webm"}

    def __init__(self, cache_service: CacheService | None = None, cache_enabled: bool = True) -> None:
        self.cache_service = cache_service
        self.cache_enabled = cache_enabled

    def scan_folder(self, folder_path: str) -> list[MediaFile]:
        folder = Path(folder_path).expanduser().resolve()
        if not folder.exists():
            raise FileNotFoundError(
                f"Thư mục nguồn không tồn tại: {folder}\n"
                "  → Hãy kiểm tra lại đường dẫn source_folder trong cấu hình."
            )
        if not folder.is_dir():
            raise NotADirectoryError(
                f"Đường dẫn nguồn không phải thư mục: {folder}\n"
                "  → source_folder phải là thư mục chứa video, không phải file."
            )

        media_files: list[MediaFile] = []
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in self.supported_extensions:
                continue

            try:
                media = self._probe_with_cache(path)
            except MissingFFmpegError:
                raise
            except (FFmpegError, FileNotFoundError, ValueError) as exc:
                logger.warning("Bỏ qua file media không hợp lệ %s: %s", path, exc)
                continue

            if media.duration < 3:
                logger.warning(
                    "Bỏ qua video quá ngắn %s: %.2fs < 3s tối thiểu", path, media.duration
                )
                continue

            media_files.append(media)

        return media_files

    def _probe_with_cache(self, path: Path) -> MediaFile:
        if self.cache_service and self.cache_service.enabled and self.cache_enabled:
            key = self.cache_service.keys.build_media_key(str(path))
            cached = self.cache_service.get_json("media_metadata", key)
            if cached:
                try:
                    return MediaFile.model_validate(cached)
                except ValueError:
                    pass

        media = probe_video(str(path))
        if self.cache_service and self.cache_service.enabled and self.cache_enabled:
            key = self.cache_service.keys.build_media_key(str(path))
            self.cache_service.set_json(key, media.model_dump(mode="json"))
        return media
