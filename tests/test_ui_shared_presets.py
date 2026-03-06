from types import SimpleNamespace

from kartencrop.ui_shared import (
    UI_STATE_DEFAULTS,
    adaptive_tile_radius,
    ensure_source_state,
    init_state,
    merged_ui_state_defaults,
    nearest_preset_label,
    normalize_persisted_ui_state,
    restore_source_state,
    sanitize_source_state,
)


def test_nearest_preset_label_returns_closest_entry() -> None:
    presets = {
        "Uebersicht": 8,
        "Standard": 9,
        "Detail": 10,
        "Sehr detailreich": 11,
    }

    assert nearest_preset_label(10, presets) == "Detail"
    assert nearest_preset_label(10.8, presets) == "Sehr detailreich"


def test_init_state_populates_combined_openaip_defaults(monkeypatch) -> None:
    fake_st = SimpleNamespace(session_state={})

    import kartencrop.ui_shared as ui_shared

    monkeypatch.setattr(ui_shared, "st", fake_st)
    monkeypatch.setattr(ui_shared, "load_persisted_ui_state", lambda: {})
    init_state()

    assert fake_st.session_state["openaip_zoom"] == 9
    assert fake_st.session_state["openaip_detail_preset"] == "Standard"
    assert fake_st.session_state["openaip_area_preset"] == "Nah"
    assert fake_st.session_state["ofm_lat"] == 52.5200
    assert fake_st.session_state["ofm_lon"] == 13.4050
    assert fake_st.session_state["ofm_start_x"] == 137
    assert fake_st.session_state["ofm_start_y"] == 83
    assert fake_st.session_state["geopf_lat"] == 48.8566
    assert fake_st.session_state["geopf_lon"] == 2.3522
    assert fake_st.session_state["geopf_start_col"] == 1037
    assert fake_st.session_state["geopf_start_row"] == 704
    assert fake_st.session_state["swiss_center_lat"] == 46.4067
    assert fake_st.session_state["swiss_center_lon"] == 8.6047
    assert fake_st.session_state["openaip_lat"] == 52.5200
    assert fake_st.session_state["openaip_lon"] == 13.4050
    assert fake_st.session_state["openaip_tile_x"] == 275
    assert fake_st.session_state["openaip_tile_y"] == 167
    assert fake_st.session_state["ui_source"] == "ofm"
    assert fake_st.session_state["ofm_render_mode_label"] == "Luftfahrtkarte (aero)"


def test_init_state_applies_persisted_values(monkeypatch) -> None:
    fake_st = SimpleNamespace(session_state={})

    import kartencrop.ui_shared as ui_shared

    monkeypatch.setattr(ui_shared, "st", fake_st)
    monkeypatch.setattr(
        ui_shared,
        "load_persisted_ui_state",
        lambda: {
            "ui_source": "swiss_wms",
            "output_directory": "C:/karten",
            "ofm_lat": 50.123456,
            "swiss_preset": "custom",
            "swiss_custom_layers": "a,b,c",
            "openaip_enabled_layers": ["airports"],
        },
    )
    init_state()

    assert fake_st.session_state["ui_source"] == "swiss_wms"
    assert fake_st.session_state["output_directory"] == "C:/karten"
    assert fake_st.session_state["ofm_lat"] == 50.123456
    assert fake_st.session_state["swiss_preset"] == "custom"
    assert fake_st.session_state["swiss_custom_layers"] == "a,b,c"
    assert fake_st.session_state["openaip_enabled_layers"] == ["airports"]
    assert fake_st.session_state["ofm_lon"] == UI_STATE_DEFAULTS["ofm_lon"]


def test_merged_ui_state_defaults_merges_persisted_values(monkeypatch) -> None:
    import kartencrop.ui_shared as ui_shared

    monkeypatch.setattr(
        ui_shared,
        "load_persisted_ui_state",
        lambda: {"geopf_lat": 47.5, "geopf_lon": 1.8},
    )

    merged = merged_ui_state_defaults()

    assert merged["geopf_lat"] == 47.5
    assert merged["geopf_lon"] == 1.8
    assert merged["ofm_lat"] == UI_STATE_DEFAULTS["ofm_lat"]


def test_restore_source_state_rehydrates_selected_source(monkeypatch) -> None:
    import kartencrop.ui_shared as ui_shared

    monkeypatch.setattr(
        ui_shared,
        "load_persisted_ui_state",
        lambda: {"geopf_lat": 48.8566, "geopf_lon": 2.3522, "geopf_output_filename": "france.png"},
    )
    state = {"geopf_lat": 0.0, "geopf_lon": 0.0, "ofm_lat": 11.0}

    restore_source_state(state, "geopf")

    assert state["geopf_lat"] == 48.8566
    assert state["geopf_lon"] == 2.3522
    assert state["geopf_output_filename"] == "france.png"
    assert state["ofm_lat"] == 11.0


def test_ensure_source_state_repairs_zero_coordinates_for_selected_source(monkeypatch) -> None:
    import kartencrop.ui_shared as ui_shared

    monkeypatch.setattr(
        ui_shared,
        "load_persisted_ui_state",
        lambda: {"openaip_lat": 0.0, "openaip_lon": 0.0, "openaip_lat_min": 0.0, "openaip_lon_min": 0.0, "openaip_lat_max": 0.0, "openaip_lon_max": 0.0},
    )
    state = {"openaip_lat": 0.0, "openaip_lon": 0.0}

    ensure_source_state(state, "openaip")

    assert state["openaip_lat"] == UI_STATE_DEFAULTS["openaip_lat"]
    assert state["openaip_lon"] == UI_STATE_DEFAULTS["openaip_lon"]
    assert state["openaip_lat_min"] == UI_STATE_DEFAULTS["openaip_lat_min"]
    assert state["openaip_lon_max"] == UI_STATE_DEFAULTS["openaip_lon_max"]


def test_sanitize_source_state_repairs_geopf_zero_bounds() -> None:
    state = {
        "geopf_lat": 48.8566,
        "geopf_lon": 2.3522,
        "geopf_lat_min": 0.0,
        "geopf_lon_min": 0.0,
        "geopf_lat_max": 0.0,
        "geopf_lon_max": 0.0,
    }

    sanitize_source_state(state, "geopf")

    assert state["geopf_lat_min"] == UI_STATE_DEFAULTS["geopf_lat_min"]
    assert state["geopf_lon_min"] == UI_STATE_DEFAULTS["geopf_lon_min"]
    assert state["geopf_lat_max"] == UI_STATE_DEFAULTS["geopf_lat_max"]
    assert state["geopf_lon_max"] == UI_STATE_DEFAULTS["geopf_lon_max"]


def test_normalize_persisted_ui_state_replaces_zero_geo_values_with_defaults() -> None:
    normalized = normalize_persisted_ui_state(
        {
            "openaip_lat": 0.0,
            "openaip_lon": 0.0,
            "geopf_lat_min": 0.0,
            "geopf_lon_min": 0.0,
            "geopf_lat_max": 0.0,
            "geopf_lon_max": 0.0,
        }
    )

    assert normalized["openaip_lat"] == UI_STATE_DEFAULTS["openaip_lat"]
    assert normalized["openaip_lon"] == UI_STATE_DEFAULTS["openaip_lon"]
    assert normalized["geopf_lat_min"] == UI_STATE_DEFAULTS["geopf_lat_min"]
    assert normalized["geopf_lon_min"] == UI_STATE_DEFAULTS["geopf_lon_min"]
    assert normalized["geopf_lat_max"] == UI_STATE_DEFAULTS["geopf_lat_max"]
    assert normalized["geopf_lon_max"] == UI_STATE_DEFAULTS["geopf_lon_max"]


def test_adaptive_tile_radius_grows_with_detail_level() -> None:
    standard = adaptive_tile_radius(base_radius=2, detail_level=9, reference_level=9, min_radius=1, max_radius=10)
    detail = adaptive_tile_radius(base_radius=2, detail_level=11, reference_level=9, min_radius=1, max_radius=10)
    very_detail = adaptive_tile_radius(base_radius=2, detail_level=13, reference_level=9, min_radius=1, max_radius=10)

    assert standard == 2
    assert detail == 8
    assert very_detail == 10


def test_adaptive_tile_radius_respects_cap() -> None:
    radius = adaptive_tile_radius(base_radius=5, detail_level=13, reference_level=9, min_radius=1, max_radius=8)
    assert radius == 8
