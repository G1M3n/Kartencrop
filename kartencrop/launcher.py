from __future__ import annotations

import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path

from streamlit.web import cli as streamlit_cli


APP_SCRIPT_NAME = "map_ui.py"
DEFAULT_PORT = 8501
MAX_PORT_ATTEMPTS = 50


def resource_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root)
    return Path(__file__).resolve().parent.parent


def resolve_app_script() -> Path:
    candidates = [
        resource_root() / APP_SCRIPT_NAME,
        Path(sys.executable).resolve().parent / APP_SCRIPT_NAME,
        Path(__file__).resolve().parent.parent / APP_SCRIPT_NAME,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    searched = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"{APP_SCRIPT_NAME} wurde nicht gefunden. Gesucht in: {searched}")


def find_available_port(start_port: int = DEFAULT_PORT, attempts: int = MAX_PORT_ATTEMPTS) -> int:
    for port in range(start_port, start_port + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"Kein freier Port im Bereich {start_port}..{start_port + attempts - 1} gefunden.")


def build_streamlit_cli_args(app_script: Path, port: int) -> list[str]:
    return [
        "streamlit",
        "run",
        str(app_script),
        "--server.headless=true",
        f"--server.port={port}",
        "--server.address=127.0.0.1",
        "--browser.serverAddress=127.0.0.1",
        "--browser.gatherUsageStats=false",
        "--server.fileWatcherType=none",
        "--global.developmentMode=false",
    ]


def open_browser_after_delay(url: str, delay_seconds: float = 1.25) -> threading.Timer:
    timer = threading.Timer(delay_seconds, lambda: webbrowser.open(url, new=2))
    timer.daemon = True
    timer.start()
    return timer


def main() -> None:
    app_script = resolve_app_script()
    port = find_available_port()
    url = f"http://127.0.0.1:{port}"
    os.chdir(app_script.parent)
    open_browser_after_delay(url)
    sys.argv = build_streamlit_cli_args(app_script, port)
    streamlit_cli.main()


if __name__ == "__main__":
    main()
