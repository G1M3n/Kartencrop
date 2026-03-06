from __future__ import annotations

import socket
import shutil
import sys
import uuid
from pathlib import Path

import pytest

from kartencrop import launcher


LOCAL_TEST_ROOT = Path(".test_artifacts")


def make_local_test_dir() -> Path:
    path = LOCAL_TEST_ROOT / f"launcher_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def test_build_streamlit_cli_args() -> None:
    args = launcher.build_streamlit_cli_args(Path("map_ui.py"), 8512)
    assert args[0:3] == ["streamlit", "run", "map_ui.py"]
    assert "--server.headless=true" in args
    assert "--server.address=127.0.0.1" in args
    assert "--browser.serverAddress=127.0.0.1" in args
    assert "--server.port=8512" in args


def test_find_available_port_returns_requested_port_when_free() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
    port = launcher.find_available_port(start_port=free_port, attempts=1)
    assert port == free_port


def test_resolve_app_script_uses_frozen_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    tmp_path = make_local_test_dir()
    try:
        bundled_script = tmp_path / "map_ui.py"
        bundled_script.write_text("print('ok')", encoding="utf-8")
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
        monkeypatch.setattr(sys, "executable", str(tmp_path / "KartencropUI.exe"))
        assert launcher.resolve_app_script() == bundled_script
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_resolve_app_script_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    tmp_path = make_local_test_dir()
    try:
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "missing_bundle"), raising=False)
        monkeypatch.setattr(sys, "executable", str(tmp_path / "missing_exe" / "KartencropUI.exe"))
        monkeypatch.setattr(launcher, "__file__", str(tmp_path / "pkg" / "launcher.py"))
        with pytest.raises(FileNotFoundError):
            launcher.resolve_app_script()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
