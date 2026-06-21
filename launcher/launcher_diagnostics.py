from __future__ import annotations

import argparse
import json
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def health_ready(url: str, timeout: float = 2.0) -> bool:
    target = url.rstrip("/") + "/api/health"
    try:
        with urllib.request.urlopen(target, timeout=timeout) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read().decode("utf-8"))
            return payload.get("status") == "ok"
    except (OSError, ValueError, urllib.error.URLError):
        return False


def port_busy(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def wait_for_health(url: str, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if health_ready(url):
            return True
        time.sleep(0.5)
    return False


def server_state_url(project_root: str) -> str | None:
    backend = Path(project_root).resolve() / "backend"
    sys.path.insert(0, str(backend))
    from app.utils.app_paths import app_data_dir

    state_path = app_data_dir() / "launcher" / "server_state.json"
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    url = str(payload.get("url") or "").strip()
    if url:
        return url
    host = str(payload.get("host") or "127.0.0.1").strip() or "127.0.0.1"
    try:
        port = int(payload.get("port") or 8000)
    except (TypeError, ValueError):
        port = 8000
    return f"http://{host}:{port}"


def wait_for_instance(project_root: str, default_url: str, timeout: float) -> str | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        candidates = []
        state_url = server_state_url(project_root)
        if state_url:
            candidates.append(state_url)
        candidates.append(default_url)
        checked: set[str] = set()
        for url in candidates:
            if not url or url in checked:
                continue
            checked.add(url)
            if health_ready(url, timeout=1.0):
                return url.rstrip("/")
        time.sleep(0.5)
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    health_parser = subparsers.add_parser("health")
    health_parser.add_argument("url")

    wait_parser = subparsers.add_parser("wait-health")
    wait_parser.add_argument("url")
    wait_parser.add_argument("--timeout", type=float, default=30.0)

    instance_parser = subparsers.add_parser("wait-instance")
    instance_parser.add_argument("project_root")
    instance_parser.add_argument("default_url")
    instance_parser.add_argument("--timeout", type=float, default=45.0)

    port_parser = subparsers.add_parser("port-busy")
    port_parser.add_argument("host")
    port_parser.add_argument("port", type=int)

    version_parser = subparsers.add_parser("python-version")
    version_parser.add_argument("--minimum", default="3.11")

    tool_parser = subparsers.add_parser("managed-tool")
    tool_parser.add_argument("project_root")
    tool_parser.add_argument("tool", choices=("ffmpeg", "ffprobe"))

    args = parser.parse_args()
    if args.command == "health":
        return 0 if health_ready(args.url) else 1
    if args.command == "wait-health":
        return 0 if wait_for_health(args.url, args.timeout) else 1
    if args.command == "wait-instance":
        url = wait_for_instance(args.project_root, args.default_url, args.timeout)
        if url:
            print(url)
            return 0
        return 1
    if args.command == "port-busy":
        return 0 if port_busy(args.host, args.port) else 1
    if args.command == "python-version":
        minimum = tuple(int(part) for part in args.minimum.split(".", maxsplit=1))
        print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        return 0 if sys.version_info[:2] >= minimum else 1
    if args.command == "managed-tool":
        backend = Path(args.project_root).resolve() / "backend"
        sys.path.insert(0, str(backend))
        from app.utils.dependency_manager import find_tool

        path = find_tool(args.tool)
        if path:
            print(path)
            return 0
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
