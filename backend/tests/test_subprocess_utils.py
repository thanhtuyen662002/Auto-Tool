import subprocess

from app.utils import subprocess_utils


def test_run_hidden_sets_create_no_window_on_windows(monkeypatch):
    calls: list[dict] = []

    monkeypatch.setattr(subprocess_utils.os, "name", "nt")
    monkeypatch.setattr(subprocess_utils.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append({"command": command, **kwargs})
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess_utils.subprocess, "run", fake_run)

    subprocess_utils.run_hidden(["ffmpeg", "-version"], check=False)

    assert calls[0]["creationflags"] == 0x08000000


def test_run_hidden_keeps_explicit_creationflags(monkeypatch):
    calls: list[dict] = []

    monkeypatch.setattr(subprocess_utils.os, "name", "nt")

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append({"command": command, **kwargs})
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess_utils.subprocess, "run", fake_run)

    subprocess_utils.run_hidden(["ffmpeg", "-version"], creationflags=123)

    assert calls[0]["creationflags"] == 123
