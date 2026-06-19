from __future__ import annotations

import importlib
import importlib.util
import logging
import os
import shutil
import subprocess
import sys
import threading
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.utils.app_paths import (
    app_data_dir,
    backend_dir,
    bundle_dir,
    bundled_vendor_dir,
    executable_dir,
    project_root,
    unique_paths,
)
from app.utils.subprocess_utils import run_hidden


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
DEFAULT_OCR_PROVIDER = "easyocr"


logger = logging.getLogger(__name__)


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
    ocr_provider: str | None = None
    ocr_available: bool = False
    ocr_auto_installed: bool = False
    ocr_message: str | None = None


@dataclass(frozen=True)
class OCRDependencyReport:
    provider: str
    available: bool
    auto_install_attempted: bool = False
    auto_installed: bool = False
    package_dir: str | None = None
    message: str | None = None
    warnings: tuple[str, ...] = ()


def auto_install_enabled() -> bool:
    value = os.getenv("AUTO_TOOL_AUTO_INSTALL", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def ocr_auto_install_enabled() -> bool:
    value = os.getenv("AUTO_TOOL_AUTO_INSTALL_OCR", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def ensure_runtime_dependencies(
    auto_install: bool | None = None,
    include_piper: bool = False,
    include_ocr: bool = False,
    ocr_provider: str = DEFAULT_OCR_PROVIDER,
    warmup_ocr_models: bool = False,
) -> RuntimeDependencyReport:
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

    ocr_report: OCRDependencyReport | None = None
    if include_ocr:
        ocr_report = ensure_ocr_dependency(
            provider=ocr_provider,
            auto_install=should_install and ocr_auto_install_enabled(),
            warmup_models=warmup_ocr_models,
        )
        warnings.extend(ocr_report.warnings)
        if ocr_report.message and not ocr_report.available:
            warnings.append(ocr_report.message)

    return RuntimeDependencyReport(
        ffmpeg_path=str(ffmpeg) if ffmpeg else None,
        ffprobe_path=str(ffprobe) if ffprobe else None,
        auto_installed=installed,
        piper_path=str(piper) if piper else None,
        piper_model_path=str(piper_model) if piper_model else None,
        piper_config_path=str(piper_config) if piper_config else None,
        piper_auto_installed=piper_installed,
        warnings=tuple(warnings),
        ocr_provider=ocr_report.provider if ocr_report else None,
        ocr_available=ocr_report.available if ocr_report else False,
        ocr_auto_installed=ocr_report.auto_installed if ocr_report else False,
        ocr_message=ocr_report.message if ocr_report else None,
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


def ensure_ocr_dependency(
    provider: str = DEFAULT_OCR_PROVIDER,
    auto_install: bool | None = None,
    warmup_models: bool = False,
    language: str = "ch",
) -> OCRDependencyReport:
    normalized = normalize_ocr_provider(provider)
    package_dir = configure_python_package_path()
    if normalized == "mock_ocr":
        return OCRDependencyReport(provider=normalized, available=True, package_dir=str(package_dir))

    module_name, packages = _ocr_module_and_packages(normalized)
    if _module_available(module_name):
        message = None
        warnings = _warmup_ocr_model(normalized, language) if warmup_models else []
        return OCRDependencyReport(
            provider=normalized,
            available=True,
            package_dir=str(package_dir),
            message=message,
            warnings=tuple(warnings),
        )

    should_install = auto_install_enabled() if auto_install is None else auto_install
    should_install = should_install and ocr_auto_install_enabled()
    if not should_install:
        return OCRDependencyReport(
            provider=normalized,
            available=False,
            package_dir=str(package_dir),
            message=_missing_ocr_message(normalized),
        )

    try:
        _install_python_packages(packages, package_dir)
    except DependencyError as exc:
        return OCRDependencyReport(
            provider=normalized,
            available=False,
            auto_install_attempted=True,
            package_dir=str(package_dir),
            message=str(exc),
        )

    importlib.invalidate_caches()
    configure_python_package_path(package_dir)
    available = _module_available(module_name)
    warnings = _warmup_ocr_model(normalized, language) if available and warmup_models else []
    return OCRDependencyReport(
        provider=normalized,
        available=available,
        auto_install_attempted=True,
        auto_installed=available,
        package_dir=str(package_dir),
        message=None if available else _missing_ocr_message(normalized),
        warnings=tuple(warnings),
    )


def normalize_ocr_provider(provider: str | None) -> str:
    normalized = (provider or DEFAULT_OCR_PROVIDER).strip().lower()
    if normalized in {"easy", "easy_ocr"}:
        return "easyocr"
    if normalized in {"paddle", "paddle_ocr"}:
        return "paddleocr"
    return normalized


def configure_python_package_path(package_dir: Path | None = None) -> Path:
    target = package_dir or local_python_package_dir()
    target.mkdir(parents=True, exist_ok=True)
    target_str = str(target)
    if target_str not in sys.path:
        sys.path.insert(0, target_str)
    current = os.environ.get("PYTHONPATH", "")
    parts = current.split(os.pathsep) if current else []
    normalized = target_str.lower() if os.name == "nt" else target_str
    if normalized not in {(part.lower() if os.name == "nt" else part) for part in parts}:
        os.environ["PYTHONPATH"] = target_str + (os.pathsep + current if current else "")
    return target


def local_python_package_dir() -> Path:
    configured = os.getenv("AUTO_TOOL_PYTHON_PACKAGES_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    version = f"py{sys.version_info.major}{sys.version_info.minor}"
    return app_data_dir() / "python_packages" / version


def _ocr_module_and_packages(provider: str) -> tuple[str, list[str]]:
    if provider == "easyocr":
        return "easyocr", ["easyocr"]
    if provider == "paddleocr":
        return "paddleocr", ["paddleocr", "paddlepaddle"]
    raise DependencyError(f"OCR provider chưa được hỗ trợ: {provider}")


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _install_python_packages(packages: list[str], target_dir: Path) -> None:
    python_command = _pip_python_command()
    if not python_command:
        raise DependencyError(
            "Không tìm thấy Python runtime phù hợp để tự cài OCR. "
            "Bản exe nên được build kèm OCR, hoặc đặt AUTO_TOOL_PYTHON_PATH tới python.exe cùng phiên bản."
        )

    target_dir.mkdir(parents=True, exist_ok=True)
    timeout_seconds = int(os.getenv("AUTO_TOOL_PIP_TIMEOUT_SECONDS", "1800"))
    command = [
        *python_command,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--target",
        str(target_dir),
        *packages,
    ]
    logger.info("Installing OCR packages into %s: %s", target_dir, " ".join(packages))
    try:
        result = run_hidden(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise DependencyError(
            f"Cài OCR timeout sau {timeout_seconds}s. Mở lại app hoặc tăng AUTO_TOOL_PIP_TIMEOUT_SECONDS."
        ) from exc
    except OSError as exc:
        raise DependencyError(f"Không thể chạy pip để cài OCR: {exc}") from exc

    if result.returncode != 0:
        details = (result.stderr or result.stdout or "").strip()
        raise DependencyError(f"Cài OCR packages thất bại: {details or 'pip returned a non-zero exit code.'}")


def _pip_python_command() -> list[str] | None:
    configured = os.getenv("AUTO_TOOL_PYTHON_PATH")
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.exists():
            return [str(candidate.resolve())]

    if not getattr(sys, "frozen", False):
        return [sys.executable]

    major = sys.version_info.major
    minor = sys.version_info.minor
    if os.name == "nt" and shutil.which("py"):
        return ["py", f"-{major}.{minor}"]
    if shutil.which("python"):
        return ["python"]
    return None


def _missing_ocr_message(provider: str) -> str:
    if provider == "easyocr":
        return "EasyOCR is not installed. Auto Tool will try to install easyocr automatically when auto-install is enabled."
    if provider == "paddleocr":
        return (
            "PaddleOCR is not installed. Auto Tool can try paddleocr+paddlepaddle, "
            "but paddlepaddle must support the current Python version."
        )
    return f"OCR provider chưa được hỗ trợ: {provider}"


def _warmup_ocr_model(provider: str, language: str) -> list[str]:
    try:
        if provider == "easyocr":
            easyocr = importlib.import_module("easyocr")
            lang = "ch_sim" if language in {"ch", "zh", "zh-cn"} else language
            easyocr.Reader([lang], gpu=False, verbose=False)
        elif provider == "paddleocr":
            paddleocr = importlib.import_module("paddleocr")
            paddleocr.PaddleOCR(use_angle_cls=True, lang=language or "ch", show_log=False)
    except Exception as exc:
        return [f"OCR model warmup failed for {provider}: {exc}"]
    return []


_DEPENDENCY_WARMUP_STARTED = False
_DEPENDENCY_WARMUP_LOCK = threading.Lock()


def start_background_dependency_warmup(
    include_piper: bool = True,
    include_ocr: bool = True,
    ocr_provider: str = DEFAULT_OCR_PROVIDER,
    warmup_ocr_models: bool = True,
) -> threading.Thread | None:
    global _DEPENDENCY_WARMUP_STARTED
    enabled = os.getenv("AUTO_TOOL_STARTUP_DEPENDENCY_WARMUP", "1").strip().lower()
    if enabled in {"0", "false", "no", "off"}:
        return None
    if "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST"):
        return None
    with _DEPENDENCY_WARMUP_LOCK:
        if _DEPENDENCY_WARMUP_STARTED:
            return None
        _DEPENDENCY_WARMUP_STARTED = True

    thread = threading.Thread(
        target=_background_dependency_warmup,
        args=(include_piper, include_ocr, ocr_provider, warmup_ocr_models),
        daemon=True,
        name="auto-tool-dependency-warmup",
    )
    thread.start()
    return thread


def _background_dependency_warmup(
    include_piper: bool,
    include_ocr: bool,
    ocr_provider: str,
    warmup_ocr_models: bool,
) -> None:
    try:
        report = ensure_runtime_dependencies(
            auto_install=None,
            include_piper=include_piper,
            include_ocr=include_ocr,
            ocr_provider=ocr_provider,
            warmup_ocr_models=warmup_ocr_models,
        )
        logger.info("Dependency warmup FFmpeg: %s", report.ffmpeg_path or "not found")
        logger.info("Dependency warmup FFprobe: %s", report.ffprobe_path or "not found")
        if include_piper:
            logger.info("Dependency warmup Piper: %s", report.piper_path or "not found")
            logger.info("Dependency warmup Piper model: %s", report.piper_model_path or "not found")
        if include_ocr:
            logger.info(
                "Dependency warmup OCR %s: %s",
                report.ocr_provider or ocr_provider,
                "available" if report.ocr_available else "not available",
            )
        for warning in report.warnings:
            logger.warning(warning)
    except Exception as exc:
        logger.warning("Runtime dependency warmup failed: %s", exc)


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

    # Bundled vendor (PyInstaller --add-data) — check first so frozen exe works offline
    vendor = bundled_vendor_dir()
    ffmpeg_vendor = vendor / "ffmpeg"
    bases.extend([
        ffmpeg_vendor,
        ffmpeg_vendor / "bin",
    ])

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

    # Bundled vendor (PyInstaller --add-data) — check first so frozen exe works offline
    vendor = bundled_vendor_dir()
    piper_vendor = vendor / "piper"
    bases.extend([
        piper_vendor,
        piper_vendor / "bin",
    ])

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

    # Bundled vendor — check first so frozen exe works offline
    vendor = bundled_vendor_dir()
    piper_vendor = vendor / "piper"
    bases.extend([
        piper_vendor / "models",
        piper_vendor,
    ])

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
