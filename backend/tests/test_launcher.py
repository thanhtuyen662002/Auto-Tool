import sys
from types import SimpleNamespace

from app import launcher


def test_launcher_host_uses_env_override(monkeypatch):
    monkeypatch.setenv("AUTO_TOOL_HOST", "127.0.0.1")

    assert launcher._launcher_host("0.0.0.0") == "127.0.0.1"


def test_launcher_port_falls_back_on_invalid_env(monkeypatch):
    monkeypatch.setenv("AUTO_TOOL_PORT", "not-a-port")

    assert launcher._launcher_port(8000) == 8000


def test_launcher_defaults_to_single_instance(monkeypatch):
    monkeypatch.delenv("AUTO_TOOL_SINGLE_INSTANCE", raising=False)

    assert launcher._single_instance_enabled() is True


def test_launcher_existing_instance_uses_state_file(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTO_TOOL_DATA_DIR", str(tmp_path))
    launcher._write_server_state("127.0.0.1", 8123)
    monkeypatch.setattr(
        launcher,
        "_auto_tool_health_ready",
        lambda host, port, timeout_seconds=0.75: host == "127.0.0.1" and port == 8123,
    )

    assert launcher._existing_instance_url("127.0.0.1", 8000) == "http://127.0.0.1:8123"


def test_launcher_existing_instance_checks_default_port(monkeypatch):
    monkeypatch.setattr(
        launcher,
        "_read_server_state",
        lambda: None,
    )
    monkeypatch.setattr(
        launcher,
        "_auto_tool_health_ready",
        lambda host, port, timeout_seconds=0.75: host == "127.0.0.1" and port == 8000,
    )

    assert launcher._existing_instance_url("127.0.0.1", 8000) == "http://127.0.0.1:8000"


def test_launcher_clears_only_current_server_state(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTO_TOOL_DATA_DIR", str(tmp_path))
    launcher._write_server_state("127.0.0.1", 8000)

    launcher._clear_server_state_if_current()

    assert launcher._read_server_state() is None


def test_launcher_instance_lock_can_be_acquired_and_released(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTO_TOOL_DATA_DIR", str(tmp_path))
    launcher._release_instance_lock()

    assert launcher._acquire_instance_lock() is True
    assert (tmp_path / "launcher" / "instance.lock").exists()

    launcher._release_instance_lock()
    assert launcher._acquire_instance_lock() is True
    launcher._release_instance_lock()


def test_launcher_uses_fallback_port_when_preferred_port_is_busy(monkeypatch):
    calls = {}
    config = SimpleNamespace(auto_open_browser=False)
    monkeypatch.setattr(launcher, "_port_available", lambda port: False if port == 8000 else True)
    monkeypatch.setattr(launcher, "_wait_for_auto_tool_health", lambda host, port, timeout_seconds=8.0: False)
    monkeypatch.setattr(launcher, "_strict_port_enabled", lambda: False)
    monkeypatch.setattr(launcher, "_find_available_port", lambda preferred: 8124)
    monkeypatch.setattr(
        launcher,
        "ensure_runtime_dependencies",
        lambda auto_install=None, include_piper=True: SimpleNamespace(
            ffmpeg_path=None,
            ffprobe_path=None,
            piper_path=None,
            piper_model_path=None,
            warnings=[],
        ),
    )
    monkeypatch.setattr(launcher, "start_background_dependency_warmup", lambda **_kwargs: None)
    monkeypatch.setattr(launcher, "create_app", lambda: object())
    monkeypatch.setattr(launcher, "_write_server_state", lambda host, port: calls.update({"state": (host, port)}))
    monkeypatch.setattr(launcher, "_clear_server_state_if_current", lambda: None)
    monkeypatch.setattr(launcher.uvicorn, "run", lambda app, host, port, reload=False: calls.update({"run": (host, port)}))

    assert launcher._run_server(config, "127.0.0.1", 8000) == 0
    assert calls["state"] == ("127.0.0.1", 8124)
    assert calls["run"] == ("127.0.0.1", 8124)


def test_launcher_refuses_fallback_port_when_strict(monkeypatch):
    config = SimpleNamespace(auto_open_browser=False)
    monkeypatch.setattr(launcher, "_port_available", lambda _port: False)
    monkeypatch.setattr(launcher, "_wait_for_auto_tool_health", lambda host, port, timeout_seconds=8.0: False)
    monkeypatch.setattr(launcher, "_strict_port_enabled", lambda: True)

    assert launcher._run_server(config, "127.0.0.1", 8000) == 1


def test_launcher_creates_stdio_streams_when_no_console(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTO_TOOL_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    launcher._ensure_stdio_streams()

    assert sys.stdout is not None
    assert sys.stderr is not None
    assert hasattr(sys.stdout, "isatty")
    assert hasattr(sys.stderr, "isatty")
    assert (tmp_path / "logs" / "launcher" / "stdout.log").exists()
    assert (tmp_path / "logs" / "launcher" / "stderr.log").exists()
