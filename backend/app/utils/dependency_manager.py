from __future__ import annotations

import os
import shutil
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.utils.app_paths import app_data_dir, backend_dir, executable_dir, project_root, unique_paths


FFMPEG_WINDOWS_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
PIPER_WINDOWS_URL = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip"
PIPER_VI_MODEL_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"
    "vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium.onnx"
)
PIPER_VI_CONFIG_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"
    "vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium.onnx.json"
)
PIPER_VI_MODEL_NAME = "vi_VN-vais1000-medium.onnx"
PIPER_VI_CONFIG_NAME = "vi_VN-vais1000-medium.onnx.json"


class DependencyError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeDependencyReport:
    ffmpeg_path: str | None
    ffprobe_path: str | None
    auto_installed: bool
    piper_path: str | None = None
    piper_model_path: str | None = None
    piper_config_path: str | None = None
    piper_auto_installed: bool = False
    warnings: tuple[str, ...] = ()


def auto_install_enabled() -> bool:
    value = os.getenv("AUTO_TOOL_AUTO_INSTALL", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def ensure_runtime_dependencies(auto_install: bool | None = None, include_piper: bool = False) -> RuntimeDependencyReport:
    should_install = auto_install_enabled() if auto_install is None else auto_install
    installed = False
    piper_installed = False
    warnings: list[str] = []
    ffmpeg = find_tool("ffmpeg")
    ffprobe = find_tool("ffprobe")

    if (not ffmpeg or not ffprobe) and should_install:
        installed = install_ffmpeg_windows()
        ffmpeg = find_tool("ffmpeg")
        ffprobe = find_tool("ffprobe")

    piper: Path | None = None
    piper_model: Path | None = None
    piper_config: Path | None = None
    if include_piper:
        piper = find_piper_tool()
        piper_model, piper_config = find_piper_voice_files()
        if should_install and (not piper or not piper_model or not piper_config):
            try:
                piper_installed = install_piper_windows()
            except DependencyError as exc:
                warnings.append(str(exc))
            piper = find_piper_tool()
            piper_model, piper_config = find_piper_voice_files()
        configure_piper_environment(piper, piper_model, piper_config)

    return RuntimeDependencyReport(
        ffmpeg_path=str(ffmpeg) if ffmpeg else None,
        ffprobe_path=str(ffprobe) if ffprobe else None,
        auto_installed=installed,
        piper_path=str(piper) if piper else None,
        piper_model_path=str(piper_model) if piper_model else None,
        piper_config_path=str(piper_config) if piper_config else None,
        piper_auto_installed=piper_installed,
        warnings=tuple(warnings),
    )


def resolve_tool(name: str) -> str:
    requested = Path(name).expanduser()
    if requested.exists():
        return str(requested.resolve())

    tool_name = Path(name).stem.lower()
    if tool_name not in {"ffmpeg", "ffprobe"}:
        return name

    found = find_tool(tool_name)
    if found:
        add_to_process_path(found.parent)
        return str(found)

    report = ensure_runtime_dependencies(auto_install=None)
    found_path = report.ffmpeg_path if tool_name == "ffmpeg" else report.ffprobe_path
    if found_path:
        found = Path(found_path)
        add_to_process_path(found.parent)
        return str(found)

    raise DependencyError(
        f"Missing {tool_name}. Auto Tool could not find or install FFmpeg. "
        "Install FFmpeg manually, put ffmpeg/ffprobe in PATH, or set AUTO_TOOL_FFMPEG_DIR."
    )


def find_tool(name: str) -> Path | None:
    exe_name = f"{name}.exe" if os.name == "nt" else name
    env_key = f"AUTO_TOOL_{name.upper()}_PATH"
    env_path = os.getenv(env_key)
    if env_path:
        candidate = Path(env_path).expanduser()
        if candidate.exists():
            return candidate.resolve()

    for directory in candidate_tool_dirs():
        candidate = directory / exe_name
        if candidate.exists():
            return candidate.resolve()

    which_result = shutil.which(exe_name) or shutil.which(name)
    if which_result:
        return Path(which_result).resolve()

    return _find_nested_tool(local_tool_root(), exe_name)


def find_piper_tool() -> Path | None:
    exe_name = "piper.exe" if os.name == "nt" else "piper"
    for env_key in ("AUTO_TOOL_PIPER_PATH", "PIPER_EXE_PATH"):
        env_path = os.getenv(env_key)
        if env_path:
            candidate = Path(env_path).expanduser()
            if candidate.exists():
                return candidate.resolve()

    for directory in piper_candidate_dirs():
        candidate = directory / exe_name
        if candidate.exists():
            return candidate.resolve()

    which_result = shutil.which(exe_name) or shutil.which("piper")
    if which_result:
        return Path(which_result).resolve()

    return _find_nested_tool(local_piper_root(), exe_name)


def find_piper_voice_files() -> tuple[Path | None, Path | None]:
    model = _existing_env_path("PIPER_MODEL_PATH")
    config = _existing_env_path("PIPER_CONFIG_PATH")
    if model and not config:
        config = _matching_piper_config(model)
    if config and not model:
        model = _matching_piper_model(config)
    if model and config:
        return model, config

    for directory in piper_model_candidate_dirs():
        exact_model = directory / PIPER_VI_MODEL_NAME
        exact_config = directory / PIPER_VI_CONFIG_NAME
        if exact_model.exists() and exact_config.exists():
            return exact_model.resolve(), exact_config.resolve()

        for candidate_model in directory.glob("*.onnx"):
            candidate_config = _matching_piper_config(candidate_model)
            if candidate_config:
                return candidate_model.resolve(), candidate_config.resolve()

    return None, None


def configure_piper_environment(
    piper: Path | None,
    model: Path | None,
    config: Path | None,
) -> None:
    if piper:
        add_to_process_path(piper.parent)
        os.environ["AUTO_TOOL_PIPER_PATH"] = str(piper)
    if model and (not os.getenv("PIPER_MODEL_PATH") or not Path(os.getenv("PIPER_MODEL_PATH", "")).exists()):
        os.environ["PIPER_MODEL_PATH"] = str(model)
    if config and (not os.getenv("PIPER_CONFIG_PATH") or not Path(os.getenv("PIPER_CONFIG_PATH", "")).exists()):
        os.environ["PIPER_CONFIG_PATH"] = str(config)


def install_ffmpeg_windows() -> bool:
    if os.name != "nt":
        return False

    try:
        root = local_tool_root()
        existing = _find_nested_tool(root, "ffmpeg.exe")
        existing_probe = _find_nested_tool(root, "ffprobe.exe")
        if existing and existing_probe:
            add_to_process_path(existing.parent)
            return False

        root.mkdir(parents=True, exist_ok=True)
        archive_path = root / "ffmpeg-release-essentials.zip"
        extract_dir = root / "ffmpeg-release-essentials"
        _download_and_extract_archive(FFMPEG_WINDOWS_URL, archive_path, extract_dir, "FFmpeg")

        ffmpeg = _find_nested_tool(extract_dir, "ffmpeg.exe")
        ffprobe = _find_nested_tool(extract_dir, "ffprobe.exe")
        if not ffmpeg or not ffprobe:
            raise DependencyError("Downloaded FFmpeg archive does not contain ffmpeg.exe and ffprobe.exe.")

        add_to_process_path(ffmpeg.parent)
        return True
    except DependencyError:
        raise
    except Exception as exc:
        raise DependencyError(f"Could not install FFmpeg automatically: {exc}") from exc


def install_piper_windows() -> bool:
    if os.name != "nt":
        return False

    try:
        root = local_piper_root()
        model_dir = local_piper_model_root()
        existing = find_piper_tool()
        existing_model, existing_config = find_piper_voice_files()
        if existing and existing_model and existing_config:
            configure_piper_environment(existing, existing_model, existing_config)
            return False

        root.mkdir(parents=True, exist_ok=True)
        model_dir.mkdir(parents=True, exist_ok=True)

        if not existing:
            archive_path = root / "piper_windows_amd64.zip"
            extract_dir = root / "piper_windows_amd64"
            _download_and_extract_archive(_piper_windows_url(), archive_path, extract_dir, "Piper")
            existing = _find_nested_tool(root, "piper.exe")
            if not existing:
                shutil.rmtree(extract_dir, ignore_errors=True)
                _download_and_extract_archive(_piper_windows_url(), archive_path, extract_dir, "Piper")
                existing = _find_nested_tool(root, "piper.exe")
            if not existing:
                raise DependencyError("Downloaded Piper archive does not contain piper.exe.")

        model_path = model_dir / PIPER_VI_MODEL_NAME
        config_path = model_dir / PIPER_VI_CONFIG_NAME
        if not model_path.exists():
            _download_file(_piper_voice_model_url(), model_path, "Piper Vietnamese voice model")
        if not config_path.exists():
            _download_file(_piper_voice_config_url(), config_path, "Piper Vietnamese voice config")
        if model_path.stat().st_size <= 0 or config_path.stat().st_size <= 0:
            raise DependencyError("Downloaded Piper Vietnamese voice files are empty.")

        configure_piper_environment(existing, model_path, config_path)
        return True
    except DependencyError:
        raise
    except Exception as exc:
        raise DependencyError(f"Could not install Piper automatically: {exc}") from exc


def candidate_tool_dirs() -> list[Path]:
    env_dir = os.getenv("AUTO_TOOL_FFMPEG_DIR")
    bases: list[Path] = []
    if env_dir:
        bases.append(Path(env_dir).expanduser())

    for root in [executable_dir(), project_root(), backend_dir(), app_data_dir()]:
        bases.extend(
            [
                root,
                root / "bin",
                root / "ffmpeg",
                root / "ffmpeg" / "bin",
                root / "tools" / "ffmpeg",
                root / "tools" / "ffmpeg" / "bin",
                root / "vendor" / "ffmpeg",
                root / "vendor" / "ffmpeg" / "bin",
            ]
        )

    nested = _find_nested_tool(local_tool_root(), "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if nested:
        bases.append(nested.parent)

    return unique_paths(bases)


def piper_candidate_dirs() -> list[Path]:
    bases: list[Path] = []
    env_dir = os.getenv("AUTO_TOOL_PIPER_DIR")
    if env_dir:
        bases.append(Path(env_dir).expanduser())

    for root in [executable_dir(), project_root(), backend_dir(), app_data_dir()]:
        bases.extend(
            [
                root,
                root / "bin",
                root / "piper",
                root / "piper" / "bin",
                root / "tools" / "piper",
                root / "tools" / "piper" / "bin",
                root / "vendor" / "piper",
                root / "vendor" / "piper" / "bin",
            ]
        )

    nested = _find_nested_tool(local_piper_root(), "piper.exe" if os.name == "nt" else "piper")
    if nested:
        bases.append(nested.parent)

    return unique_paths(bases)


def piper_model_candidate_dirs() -> list[Path]:
    bases: list[Path] = []
    env_dir = os.getenv("AUTO_TOOL_PIPER_MODEL_DIR")
    if env_dir:
        bases.append(Path(env_dir).expanduser())

    for root in [executable_dir(), project_root(), backend_dir(), app_data_dir(), local_piper_root()]:
        bases.extend(
            [
                root,
                root / "models",
                root / "piper" / "models",
                root / "tools" / "piper" / "models",
                root / "vendor" / "piper" / "models",
            ]
        )

    return [path for path in unique_paths(bases) if path.exists()]


def local_tool_root() -> Path:
    configured = os.getenv("AUTO_TOOL_TOOLS_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return app_data_dir() / "tools" / "ffmpeg"


def local_piper_root() -> Path:
    configured = os.getenv("AUTO_TOOL_PIPER_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return app_data_dir() / "tools" / "piper"


def local_piper_model_root() -> Path:
    configured = os.getenv("AUTO_TOOL_PIPER_MODEL_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return local_piper_root() / "models"


def add_to_process_path(directory: Path) -> None:
    directory = directory.resolve()
    current = os.environ.get("PATH", "")
    parts = current.split(os.pathsep) if current else []
    normalized = str(directory).lower() if os.name == "nt" else str(directory)
    if normalized not in {(part.lower() if os.name == "nt" else part) for part in parts}:
        os.environ["PATH"] = str(directory) + os.pathsep + current


def _download_and_extract_archive(url: str, archive_path: Path, extract_dir: Path, label: str) -> None:
    if extract_dir.exists():
        return

    last_error: Exception | None = None
    for _ in range(2):
        try:
            if archive_path.exists() and archive_path.stat().st_size <= 0:
                archive_path.unlink(missing_ok=True)
            if not archive_path.exists():
                temp_path = archive_path.with_suffix(".zip.download")
                temp_path.unlink(missing_ok=True)
                with _open_url(url, timeout=120) as response:
                    with temp_path.open("wb") as target:
                        shutil.copyfileobj(response, target)
                if temp_path.stat().st_size <= 0:
                    raise DependencyError(f"Downloaded {label} archive is empty.")
                temp_path.replace(archive_path)

            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(extract_dir)
            return
        except (zipfile.BadZipFile, DependencyError, OSError) as exc:
            last_error = exc
            archive_path.unlink(missing_ok=True)
            shutil.rmtree(extract_dir, ignore_errors=True)

    raise DependencyError(f"Downloaded {label} archive is invalid or unavailable: {last_error}")


def _download_file(url: str, output_path: Path, label: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for _ in range(2):
        temp_path = output_path.with_suffix(output_path.suffix + ".download")
        try:
            temp_path.unlink(missing_ok=True)
            with _open_url(url, timeout=180) as response:
                with temp_path.open("wb") as target:
                    shutil.copyfileobj(response, target)
            if temp_path.stat().st_size <= 0:
                raise DependencyError(f"Downloaded {label} is empty.")
            temp_path.replace(output_path)
            return
        except (DependencyError, OSError) as exc:
            last_error = exc
            temp_path.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)
    raise DependencyError(f"Could not download {label}: {last_error}")


def _open_url(url: str, timeout: float):
    request = urllib.request.Request(url, headers={"User-Agent": "AutoTool/1.0"})
    return urllib.request.urlopen(request, timeout=timeout)


def _existing_env_path(env_key: str) -> Path | None:
    value = os.getenv(env_key)
    if not value:
        return None
    path = Path(value).expanduser()
    return path.resolve() if path.exists() else None


def _matching_piper_config(model_path: Path) -> Path | None:
    candidates = [
        Path(str(model_path) + ".json"),
        model_path.with_suffix(model_path.suffix + ".json"),
        model_path.with_suffix(".onnx.json"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def _matching_piper_model(config_path: Path) -> Path | None:
    name = config_path.name
    if name.endswith(".onnx.json"):
        candidate = config_path.with_name(name.removesuffix(".json"))
        if candidate.exists():
            return candidate.resolve()
    return None


def _piper_windows_url() -> str:
    return os.getenv("AUTO_TOOL_PIPER_WINDOWS_URL", PIPER_WINDOWS_URL)


def _piper_voice_model_url() -> str:
    return os.getenv("AUTO_TOOL_PIPER_VOICE_MODEL_URL", PIPER_VI_MODEL_URL)


def _piper_voice_config_url() -> str:
    return os.getenv("AUTO_TOOL_PIPER_VOICE_CONFIG_URL", PIPER_VI_CONFIG_URL)


def _find_nested_tool(root: Path, exe_name: str) -> Path | None:
    if not root.exists():
        return None
    direct_matches = list(root.glob(f"*/bin/{exe_name}")) + list(root.glob(f"**/bin/{exe_name}"))
    for match in direct_matches:
        if match.exists():
            return match.resolve()
    for match in root.glob(f"**/{exe_name}"):
        if match.exists():
            return match.resolve()
    return None
