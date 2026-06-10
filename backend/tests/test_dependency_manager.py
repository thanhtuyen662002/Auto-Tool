from __future__ import annotations

import os
from pathlib import Path

from app.utils import dependency_manager


def test_configure_piper_environment_sets_runtime_paths(tmp_path, monkeypatch):
    monkeypatch.delenv("AUTO_TOOL_PIPER_PATH", raising=False)
    monkeypatch.delenv("PIPER_MODEL_PATH", raising=False)
    monkeypatch.delenv("PIPER_CONFIG_PATH", raising=False)
    monkeypatch.setenv("PATH", "")

    piper = tmp_path / "bin" / "piper.exe"
    model = tmp_path / "models" / "vi_VN-vais1000-medium.onnx"
    config = tmp_path / "models" / "vi_VN-vais1000-medium.onnx.json"
    piper.parent.mkdir(parents=True)
    model.parent.mkdir(parents=True)
    piper.write_bytes(b"exe")
    model.write_bytes(b"model")
    config.write_text("{}", encoding="utf-8")

    dependency_manager.configure_piper_environment(piper, model, config)

    assert os.environ["AUTO_TOOL_PIPER_PATH"] == str(piper)
    assert os.environ["PIPER_MODEL_PATH"] == str(model)
    assert os.environ["PIPER_CONFIG_PATH"] == str(config)
    assert str(piper.parent) in os.environ["PATH"].split(os.pathsep)


def test_find_piper_voice_files_discovers_default_model_names(tmp_path, monkeypatch):
    monkeypatch.delenv("PIPER_MODEL_PATH", raising=False)
    monkeypatch.delenv("PIPER_CONFIG_PATH", raising=False)
    monkeypatch.setenv("AUTO_TOOL_PIPER_MODEL_DIR", str(tmp_path))

    model = tmp_path / "vi_VN-vais1000-medium.onnx"
    config = tmp_path / "vi_VN-vais1000-medium.onnx.json"
    model.write_bytes(b"model")
    config.write_text("{}", encoding="utf-8")

    found_model, found_config = dependency_manager.find_piper_voice_files()

    assert found_model == model.resolve()
    assert found_config == config.resolve()


def test_configure_python_package_path_adds_local_target(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTO_TOOL_PYTHON_PACKAGES_DIR", str(tmp_path))
    monkeypatch.setenv("PYTHONPATH", "")

    target = dependency_manager.configure_python_package_path()

    assert target == tmp_path.resolve()
    assert str(target) in os.sys.path
    assert str(target) in os.environ["PYTHONPATH"].split(os.pathsep)


def test_ensure_ocr_dependency_auto_installs_missing_easyocr(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTO_TOOL_PYTHON_PACKAGES_DIR", str(tmp_path))
    available = {"easyocr": False}
    installs: list[tuple[list[str], Path]] = []

    def fake_module_available(name: str) -> bool:
        return available.get(name, False)

    def fake_install(packages: list[str], target_dir: Path) -> None:
        installs.append((packages, target_dir))
        available["easyocr"] = True

    monkeypatch.setattr(dependency_manager, "_module_available", fake_module_available)
    monkeypatch.setattr(dependency_manager, "_install_python_packages", fake_install)

    report = dependency_manager.ensure_ocr_dependency("easyocr", auto_install=True)

    assert report.available is True
    assert report.auto_install_attempted is True
    assert report.auto_installed is True
    assert installs == [(["easyocr"], tmp_path.resolve())]


def test_start_background_dependency_warmup_is_skipped_under_pytest():
    assert dependency_manager.start_background_dependency_warmup() is None
