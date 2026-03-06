from pathlib import Path
import shutil
import uuid

from kartencrop.ui_persistence import (
    clear_persisted_ui_state,
    capture_persistable_state,
    load_persisted_ui_state,
    persist_ui_state,
    should_persist_ui_key,
)


def test_should_persist_ui_key_filters_project_state() -> None:
    assert should_persist_ui_key("ui_source") is True
    assert should_persist_ui_key("ofm_lat") is True
    assert should_persist_ui_key("openaip_enabled_layers") is True
    assert should_persist_ui_key("ofm_output_filename") is True
    assert should_persist_ui_key("random_runtime_value") is False


def test_capture_persistable_state_filters_non_json_values() -> None:
    state = {
        "ui_source": "ofm",
        "ofm_lat": 52.52,
        "openaip_enabled_layers": ["airports", "navaids"],
        "runtime_object": object(),
        "other": 123,
    }

    captured = capture_persistable_state(state)

    assert captured == {
        "ui_source": "ofm",
        "ofm_lat": 52.52,
        "openaip_enabled_layers": ["airports", "navaids"],
    }


def test_persist_and_load_ui_state_roundtrip() -> None:
    tmp_path = Path.cwd() / "outputs" / "test_cache" / f"case_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    try:
        target = tmp_path / "ui_state.json"
        source_state = {
            "ui_source": "swiss_wms",
            "output_directory": "C:/karten",
            "swiss_preset": "custom",
            "swiss_custom_layers": "a,b,c",
            "openaip_enabled_layers": ["airports"],
        }

        persist_ui_state(source_state, path=target)
        loaded = load_persisted_ui_state(path=target)

        assert loaded == source_state
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_load_persisted_ui_state_ignores_invalid_json() -> None:
    tmp_path = Path.cwd() / "outputs" / "test_cache" / f"case_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    try:
        target = tmp_path / "ui_state.json"
        target.write_text("{broken", encoding="utf-8")
        assert load_persisted_ui_state(path=target) == {}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_clear_persisted_ui_state_removes_file() -> None:
    tmp_path = Path.cwd() / "outputs" / "test_cache" / f"case_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    try:
        target = tmp_path / "ui_state.json"
        target.write_text("{}", encoding="utf-8")
        clear_persisted_ui_state(path=target)
        assert not target.exists()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
