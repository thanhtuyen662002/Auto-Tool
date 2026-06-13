from app import launcher


def test_launcher_host_uses_env_override(monkeypatch):
    monkeypatch.setenv("AUTO_TOOL_HOST", "127.0.0.1")

    assert launcher._launcher_host("0.0.0.0") == "127.0.0.1"


def test_launcher_port_falls_back_on_invalid_env(monkeypatch):
    monkeypatch.setenv("AUTO_TOOL_PORT", "not-a-port")

    assert launcher._launcher_port(8000) == 8000

