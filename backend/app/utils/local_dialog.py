from __future__ import annotations

from pathlib import Path

from app.utils.app_paths import project_root


class LocalDialogError(RuntimeError):
    """Raised when the local desktop file dialog cannot be opened."""


def browse_local_path(
    mode: str,
    title: str | None = None,
    initial_path: str | None = None,
    extensions: list[str] | None = None,
) -> str | None:
    """Open a native local file/folder picker and return the selected absolute path."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:  # pragma: no cover - depends on local Python/Tk install
        raise LocalDialogError("Không mở được hộp thoại chọn file/folder vì thiếu Tkinter.") from exc

    normalized_mode = mode.strip().lower()
    if normalized_mode not in {"file", "folder"}:
        raise LocalDialogError(f"Loại chọn đường dẫn không hợp lệ: {mode}")

    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()

        initial_dir = _initial_dir(initial_path)
        if normalized_mode == "folder":
            selected = filedialog.askdirectory(
                parent=root,
                title=title or "Chọn thư mục",
                initialdir=initial_dir,
                mustexist=False,
            )
        else:
            selected = filedialog.askopenfilename(
                parent=root,
                title=title or "Chọn file",
                initialdir=initial_dir,
                filetypes=_filetypes(extensions),
            )

        cleaned = str(selected or "").strip()
        return str(Path(cleaned).expanduser().resolve()) if cleaned else None
    except LocalDialogError:
        raise
    except Exception as exc:  # pragma: no cover - depends on desktop shell state
        raise LocalDialogError(f"Không mở được hộp thoại chọn đường dẫn: {exc}") from exc
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass


def _initial_dir(initial_path: str | None) -> str:
    if not initial_path:
        return str(project_root())

    path = Path(initial_path).expanduser()
    if not path.is_absolute():
        path = project_root() / path
    if path.is_file():
        return str(path.parent.resolve())
    if path.is_dir():
        return str(path.resolve())
    parent = path.parent
    return str(parent.resolve()) if parent.exists() else str(project_root())


def _filetypes(extensions: list[str] | None) -> list[tuple[str, str]]:
    cleaned = []
    for item in extensions or []:
        ext = item.strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        cleaned.append(ext)

    if not cleaned:
        return [("Tất cả file", "*.*")]

    patterns = " ".join(f"*{ext}" for ext in cleaned)
    return [("File được hỗ trợ", patterns), ("Tất cả file", "*.*")]
