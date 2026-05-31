from __future__ import annotations

from pathlib import Path

from app.adapters.ffmpeg_adapter import FFmpegError, MissingFFmpegError, probe_video
from app.schemas.media_schema import MediaFile
from app.utils.logger import get_logger


logger = get_logger(__name__)


class MediaScanner:
    supported_extensions = {".mp4", ".mov", ".mkv", ".webm"}

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
                media = probe_video(str(path))
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

