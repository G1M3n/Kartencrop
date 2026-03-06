from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


UI_STATE_PATH = Path.cwd() / "outputs" / "config" / "ui_state.json"
PERSISTED_KEY_PREFIXES = ("ui_", "ofm_", "geopf_", "swiss_", "openaip_")
PERSISTED_EXACT_KEYS = {"output_directory"}


def ui_state_path() -> Path:
    return UI_STATE_PATH


def should_persist_ui_key(key: str) -> bool:
    if key in PERSISTED_EXACT_KEYS:
        return True
    if key.endswith("_output_filename"):
        return True
    return key.startswith(PERSISTED_KEY_PREFIXES)


def _is_json_compatible(value: Any) -> bool:
    if value is None or isinstance(value, (bool, int, float, str)):
        return True
    if isinstance(value, list):
        return all(_is_json_compatible(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _is_json_compatible(item) for key, item in value.items())
    return False


def capture_persistable_state(session_state: Mapping[str, Any]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for key, value in session_state.items():
        if not should_persist_ui_key(str(key)):
            continue
        if not _is_json_compatible(value):
            continue
        data[str(key)] = value
    return data


def load_persisted_ui_state(path: Path | None = None) -> dict[str, Any]:
    target = path or ui_state_path()
    if not target.exists():
        return {}
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}

    data: dict[str, Any] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            continue
        if not should_persist_ui_key(key):
            continue
        if not _is_json_compatible(value):
            continue
        data[key] = value
    return data


def persist_ui_state(session_state: Mapping[str, Any], path: Path | None = None) -> Path:
    target = path or ui_state_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    data = capture_persistable_state(session_state)
    temp_path = target.with_suffix(f"{target.suffix}.tmp")
    temp_path.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")
    temp_path.replace(target)
    return target


def clear_persisted_ui_state(path: Path | None = None) -> None:
    target = path or ui_state_path()
    try:
        if target.exists():
            target.unlink()
    except OSError:
        pass
