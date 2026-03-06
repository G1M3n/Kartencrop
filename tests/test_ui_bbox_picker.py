from kartencrop.ui_bbox_picker import (
    LatLonBounds,
    LatLonPoint,
    apply_bbox_to_session_state,
    apply_center_to_session_state,
    bounds_from_component_value,
    current_source_bbox,
    current_source_center,
    point_from_component_value,
    point_from_map_click,
    rectangle_bounds_from_feature,
)
from kartencrop.geo import bbox_to_tile_bounds, tile_bounds_to_geo_bounds
from kartencrop.ui_shared import SOURCE_GEOPF, SOURCE_OFM, SOURCE_OPENAIP, SOURCE_SWISS, UI_STATE_DEFAULTS


def test_rectangle_bounds_from_feature_extracts_bounds() -> None:
    feature = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [13.1, 52.3],
                    [13.8, 52.3],
                    [13.8, 52.7],
                    [13.1, 52.7],
                    [13.1, 52.3],
                ]
            ],
        }
    }

    bounds = rectangle_bounds_from_feature(feature)

    assert bounds == LatLonBounds(lat_min=52.3, lon_min=13.1, lat_max=52.7, lon_max=13.8)


def test_point_from_map_click_extracts_coordinates() -> None:
    point = point_from_map_click({"lat": 52.52, "lng": 13.405})
    assert point == LatLonPoint(lat=52.52, lon=13.405)


def test_point_from_component_value_extracts_coordinates() -> None:
    point = point_from_component_value({"point": {"lat": 52.52, "lon": 13.405}})
    assert point == LatLonPoint(lat=52.52, lon=13.405)


def test_bounds_from_component_value_extracts_bounds() -> None:
    bounds = bounds_from_component_value(
        {
            "bounds": {
                "lat_min": 52.3,
                "lon_min": 13.1,
                "lat_max": 52.7,
                "lon_max": 13.8,
            }
        }
    )
    assert bounds == LatLonBounds(lat_min=52.3, lon_min=13.1, lat_max=52.7, lon_max=13.8)


def test_apply_bbox_to_session_state_updates_ofm_frame() -> None:
    state: dict[str, object] = {}
    bounds = LatLonBounds(lat_min=35.0, lon_min=-5.0, lat_max=40.0, lon_max=2.0)

    apply_bbox_to_session_state(state, SOURCE_OFM, bounds)

    assert state["ofm_area_mode"] == "Geographischer Rahmen"
    assert state["ofm_lat_min"] == 35.0
    assert state["ofm_lon_max"] == 2.0
    assert state["ofm_lat"] == 37.5
    assert state["ofm_lon"] == -1.5


def test_apply_bbox_to_session_state_updates_swiss_frame() -> None:
    state: dict[str, object] = {}
    bounds = LatLonBounds(lat_min=46.0, lon_min=8.0, lat_max=46.5, lon_max=8.5)

    apply_bbox_to_session_state(state, SOURCE_SWISS, bounds)

    assert state["swiss_bbox_mode"] == "Geographischer Rahmen"
    assert state["swiss_lat_min"] == 46.0
    assert state["swiss_lon_max"] == 8.5
    assert state["swiss_center_lat"] == 46.25
    assert state["swiss_center_lon"] == 8.25


def test_apply_center_to_session_state_updates_ofm_point() -> None:
    state: dict[str, object] = {}

    apply_center_to_session_state(state, SOURCE_OFM, LatLonPoint(lat=52.52, lon=13.405))

    assert state["ofm_area_mode"] == "GPS-Mittelpunkt"
    assert state["ofm_lat"] == 52.52
    assert state["ofm_lon"] == 13.405


def test_apply_center_to_session_state_updates_swiss_point() -> None:
    state: dict[str, object] = {}

    apply_center_to_session_state(state, SOURCE_SWISS, LatLonPoint(lat=46.4067, lon=8.6047))

    assert state["swiss_bbox_mode"] == "GPS-Mittelpunkt"
    assert state["swiss_center_lat"] == 46.4067
    assert state["swiss_center_lon"] == 8.6047


def test_current_source_center_uses_geographic_frame_when_active() -> None:
    session_state = {
        "geopf_area_mode": "Geographischer Rahmen",
        "geopf_lat_min": 45.0,
        "geopf_lon_min": 1.0,
        "geopf_lat_max": 47.0,
        "geopf_lon_max": 3.0,
    }

    center = current_source_center(session_state, SOURCE_GEOPF)

    expected_bounds = tile_bounds_to_geo_bounds(bbox_to_tile_bounds(45.0, 1.0, 47.0, 3.0, UI_STATE_DEFAULTS["geopf_tilematrix"]))
    assert center == (expected_bounds.center_lat, expected_bounds.center_lon)


def test_current_source_bbox_returns_none_for_point_mode() -> None:
    session_state = {
        "openaip_area_mode": "GPS-Mittelpunkt",
        "openaip_lat_min": 52.3,
        "openaip_lon_min": 13.1,
        "openaip_lat_max": 52.7,
        "openaip_lon_max": 13.8,
    }

    assert current_source_bbox(session_state, SOURCE_OPENAIP) is None


def test_current_source_center_uses_defaults_instead_of_zero_bbox() -> None:
    session_state = {
        "geopf_area_mode": "Geographischer Rahmen",
        "geopf_lat_min": 0.0,
        "geopf_lon_min": 0.0,
        "geopf_lat_max": 0.0,
        "geopf_lon_max": 0.0,
    }

    center = current_source_center(session_state, SOURCE_GEOPF)

    expected_bounds = tile_bounds_to_geo_bounds(
        bbox_to_tile_bounds(
            UI_STATE_DEFAULTS["geopf_lat_min"],
            UI_STATE_DEFAULTS["geopf_lon_min"],
            UI_STATE_DEFAULTS["geopf_lat_max"],
            UI_STATE_DEFAULTS["geopf_lon_max"],
            UI_STATE_DEFAULTS["geopf_tilematrix"],
        )
    )
    assert center == (expected_bounds.center_lat, expected_bounds.center_lon)


def test_current_source_bbox_uses_effective_ofm_tile_frame() -> None:
    session_state = {
        "ofm_area_mode": "Geographischer Rahmen",
        "ofm_zoom": 9,
        "ofm_lat_min": 52.48,
        "ofm_lon_min": 13.35,
        "ofm_lat_max": 52.56,
        "ofm_lon_max": 13.48,
    }

    bbox = current_source_bbox(session_state, SOURCE_OFM)

    expected = tile_bounds_to_geo_bounds(bbox_to_tile_bounds(52.48, 13.35, 52.56, 13.48, 9))
    assert bbox == LatLonBounds(
        lat_min=expected.lat_min,
        lon_min=expected.lon_min,
        lat_max=expected.lat_max,
        lon_max=expected.lon_max,
    )


def test_current_source_bbox_changes_with_ofm_zoom() -> None:
    low_zoom_state = {
        "ofm_area_mode": "Geographischer Rahmen",
        "ofm_zoom": 8,
        "ofm_lat_min": 52.48,
        "ofm_lon_min": 13.35,
        "ofm_lat_max": 52.56,
        "ofm_lon_max": 13.48,
    }
    high_zoom_state = dict(low_zoom_state)
    high_zoom_state["ofm_zoom"] = 11

    low_zoom_bbox = current_source_bbox(low_zoom_state, SOURCE_OFM)
    high_zoom_bbox = current_source_bbox(high_zoom_state, SOURCE_OFM)

    assert low_zoom_bbox is not None
    assert high_zoom_bbox is not None
    assert (high_zoom_bbox.lon_max - high_zoom_bbox.lon_min) < (low_zoom_bbox.lon_max - low_zoom_bbox.lon_min)
