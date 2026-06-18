import sys

from app import launcher


def test_launcher_host_uses_env_override(monkeypatch):
    monkeypatch.setenv("AUTO_TOOL_HOST", "127.0.0.1")

    assert launcher._launcher_host("0.0.0.0") == "127.0.0.1"


def test_launcher_port_falls_back_on_invalid_env(monkeypatch):
    monkeypatch.setenv("AUTO_TOOL_PORT", "not-a-port")

    assert launcher._launcher_port(8000) == 8000


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
