from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping

import streamlit as st

from .geo import bbox_to_tile_bounds, tile_bounds_to_geo_bounds, TileBounds
from .leaflet_picker_component import render_leaflet_picker
from .providers import geopf_scan_oaci_limits
from .tiles import Bounds, clip_bounds
from .ui_shared import (
    SOURCE_GEOPF,
    SOURCE_OFM,
    SOURCE_OPENAIP,
    SOURCE_OPENAIP_COMPOSITE,
    SOURCE_OPENAIP_PNG,
    SOURCE_SWISS,
    UI_STATE_DEFAULTS,
)


@dataclass(frozen=True)
class LatLonBounds:
    lat_min: float
    lon_min: float
    lat_max: float
    lon_max: float

    @property
    def center_lat(self) -> float:
        return (self.lat_min + self.lat_max) / 2.0

    @property
    def center_lon(self) -> float:
        return (self.lon_min + self.lon_max) / 2.0


@dataclass(frozen=True)
class LatLonPoint:
    lat: float
    lon: float


PICKER_STATE_KEY_TEMPLATE = "bbox_picker_selection_{source}"
PICKER_POINT_STATE_KEY_TEMPLATE = "bbox_picker_point_{source}"
PICKER_RESET_KEY_TEMPLATE = "bbox_picker_reset_{source}"
PICKER_EVENT_KEY_TEMPLATE = "bbox_picker_event_{source}"
ESRI_TILE_URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}"
ESRI_ATTRIBUTION = "Tiles &copy; Esri"


def picker_state_key(source: str) -> str:
    return PICKER_STATE_KEY_TEMPLATE.format(source=source)


def picker_point_state_key(source: str) -> str:
    return PICKER_POINT_STATE_KEY_TEMPLATE.format(source=source)


def picker_reset_key(source: str) -> str:
    return PICKER_RESET_KEY_TEMPLATE.format(source=source)


def picker_event_key(source: str) -> str:
    return PICKER_EVENT_KEY_TEMPLATE.format(source=source)


def _source_prefix(source: str) -> str:
    if source == SOURCE_OPENAIP:
        return "openaip"
    if source == SOURCE_OFM:
        return "ofm"
    if source == SOURCE_GEOPF:
        return "geopf"
    if source == SOURCE_SWISS:
        return "swiss"
    return source


def _state_float(session_state: Mapping[str, Any], key: str) -> float:
    return float(session_state.get(key, UI_STATE_DEFAULTS[key]))


def _normalized_bounds(
    *,
    lat_min: float,
    lon_min: float,
    lat_max: float,
    lon_max: float,
    default_lat_min: float,
    default_lon_min: float,
    default_lat_max: float,
    default_lon_max: float,
) -> LatLonBounds:
    is_valid = (
        -90.0 <= lat_min <= 90.0
        and -90.0 <= lat_max <= 90.0
        and -180.0 <= lon_min <= 180.0
        and -180.0 <= lon_max <= 180.0
        and lat_max > lat_min
        and lon_max > lon_min
    )
    if not is_valid:
        return LatLonBounds(
            lat_min=default_lat_min,
            lon_min=default_lon_min,
            lat_max=default_lat_max,
            lon_max=default_lon_max,
        )
    return LatLonBounds(lat_min=lat_min, lon_min=lon_min, lat_max=lat_max, lon_max=lon_max)


def _tile_source_zoom(session_state: Mapping[str, Any], source: str) -> int | None:
    if source == SOURCE_OFM:
        return int(session_state.get("ofm_zoom", UI_STATE_DEFAULTS["ofm_zoom"]))
    if source == SOURCE_GEOPF:
        return int(session_state.get("geopf_tilematrix", UI_STATE_DEFAULTS["geopf_tilematrix"]))
    if source in {SOURCE_OPENAIP, SOURCE_OPENAIP_PNG, SOURCE_OPENAIP_COMPOSITE}:
        return int(session_state.get("openaip_zoom", UI_STATE_DEFAULTS["openaip_zoom"]))
    return None


def _effective_tile_source_bounds(
    session_state: Mapping[str, Any],
    source: str,
    requested_bounds: LatLonBounds,
) -> LatLonBounds | None:
    zoom = _tile_source_zoom(session_state, source)
    if zoom is None:
        return requested_bounds

    tile_bounds = bbox_to_tile_bounds(
        requested_bounds.lat_min,
        requested_bounds.lon_min,
        requested_bounds.lat_max,
        requested_bounds.lon_max,
        zoom,
    )

    if source == SOURCE_GEOPF:
        limits = geopf_scan_oaci_limits()
        if zoom not in limits:
            return None
        min_col, max_col, min_row, max_row = limits[zoom]
        clipped = clip_bounds(
            Bounds(tile_bounds.min_x, tile_bounds.max_x, tile_bounds.min_y, tile_bounds.max_y),
            min_x=min_col,
            max_x=max_col,
            min_y=min_row,
            max_y=max_row,
        )
        if clipped is None:
            return None
        tile_bounds = TileBounds(clipped.min_x, clipped.max_x, clipped.min_y, clipped.max_y, zoom)

    geo_bounds = tile_bounds_to_geo_bounds(tile_bounds)
    return LatLonBounds(
        lat_min=geo_bounds.lat_min,
        lon_min=geo_bounds.lon_min,
        lat_max=geo_bounds.lat_max,
        lon_max=geo_bounds.lon_max,
    )


def current_source_center(session_state: Mapping[str, Any], source: str) -> tuple[float, float]:
    prefix = _source_prefix(source)
    if source == SOURCE_SWISS and session_state.get("swiss_bbox_mode") == "Geographischer Rahmen":
        bounds = current_source_bbox(session_state, source)
        if bounds is not None:
            return bounds.center_lat, bounds.center_lon
    if source in {SOURCE_OFM, SOURCE_GEOPF, SOURCE_OPENAIP} and session_state.get(f"{prefix}_area_mode") == "Geographischer Rahmen":
        bounds = current_source_bbox(session_state, source)
        if bounds is not None:
            return bounds.center_lat, bounds.center_lon
    if source == SOURCE_SWISS:
        return _state_float(session_state, "swiss_center_lat"), _state_float(session_state, "swiss_center_lon")
    return _state_float(session_state, f"{prefix}_lat"), _state_float(session_state, f"{prefix}_lon")


def current_source_bbox(session_state: Mapping[str, Any], source: str) -> LatLonBounds | None:
    prefix = _source_prefix(source)
    if source == SOURCE_SWISS:
        if session_state.get("swiss_bbox_mode") != "Geographischer Rahmen":
            return None
        return _normalized_bounds(
            lat_min=_state_float(session_state, "swiss_lat_min"),
            lon_min=_state_float(session_state, "swiss_lon_min"),
            lat_max=_state_float(session_state, "swiss_lat_max"),
            lon_max=_state_float(session_state, "swiss_lon_max"),
            default_lat_min=float(UI_STATE_DEFAULTS["swiss_lat_min"]),
            default_lon_min=float(UI_STATE_DEFAULTS["swiss_lon_min"]),
            default_lat_max=float(UI_STATE_DEFAULTS["swiss_lat_max"]),
            default_lon_max=float(UI_STATE_DEFAULTS["swiss_lon_max"]),
        )
    if session_state.get(f"{prefix}_area_mode") != "Geographischer Rahmen":
        return None
    requested_bounds = _normalized_bounds(
        lat_min=_state_float(session_state, f"{prefix}_lat_min"),
        lon_min=_state_float(session_state, f"{prefix}_lon_min"),
        lat_max=_state_float(session_state, f"{prefix}_lat_max"),
        lon_max=_state_float(session_state, f"{prefix}_lon_max"),
        default_lat_min=float(UI_STATE_DEFAULTS[f"{prefix}_lat_min"]),
        default_lon_min=float(UI_STATE_DEFAULTS[f"{prefix}_lon_min"]),
        default_lat_max=float(UI_STATE_DEFAULTS[f"{prefix}_lat_max"]),
        default_lon_max=float(UI_STATE_DEFAULTS[f"{prefix}_lon_max"]),
    )
    return _effective_tile_source_bounds(session_state, source, requested_bounds)


def suggested_picker_zoom(session_state: Mapping[str, Any], source: str) -> int:
    if source == SOURCE_OFM:
        return max(4, min(10, int(session_state.get("ofm_zoom", 8))))
    if source == SOURCE_GEOPF:
        return max(4, min(10, int(session_state.get("geopf_tilematrix", 9))))
    if source == SOURCE_OPENAIP:
        return max(4, min(11, int(session_state.get("openaip_zoom", 9))))
    return 10


def rectangle_bounds_from_feature(feature: Mapping[str, Any] | None) -> LatLonBounds | None:
    if not feature:
        return None
    geometry = feature.get("geometry")
    if not isinstance(geometry, Mapping):
        return None
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or not coordinates:
        return None
    polygon = coordinates[0]
    if not isinstance(polygon, list):
        return None

    lats: list[float] = []
    lons: list[float] = []
    for point in polygon:
        if not isinstance(point, list) or len(point) < 2:
            continue
        lon, lat = point[0], point[1]
        lats.append(float(lat))
        lons.append(float(lon))
    if not lats or not lons:
        return None
    return LatLonBounds(
        lat_min=min(lats),
        lon_min=min(lons),
        lat_max=max(lats),
        lon_max=max(lons),
    )


def point_from_map_click(point: Mapping[str, Any] | None) -> LatLonPoint | None:
    if not point:
        return None
    lat = point.get("lat")
    lon = point.get("lng")
    if lat is None or lon is None:
        return None
    return LatLonPoint(lat=float(lat), lon=float(lon))


def point_from_component_value(value: Mapping[str, Any] | None) -> LatLonPoint | None:
    if not isinstance(value, Mapping):
        return None
    point = value.get("point")
    if not isinstance(point, Mapping):
        return None
    lat = point.get("lat")
    lon = point.get("lon")
    if lat is None or lon is None:
        return None
    return LatLonPoint(lat=float(lat), lon=float(lon))


def bounds_from_component_value(value: Mapping[str, Any] | None) -> LatLonBounds | None:
    if not isinstance(value, Mapping):
        return None
    bounds = value.get("bounds")
    if not isinstance(bounds, Mapping):
        return None
    required = ("lat_min", "lon_min", "lat_max", "lon_max")
    if any(bounds.get(key) is None for key in required):
        return None
    return LatLonBounds(
        lat_min=float(bounds["lat_min"]),
        lon_min=float(bounds["lon_min"]),
        lat_max=float(bounds["lat_max"]),
        lon_max=float(bounds["lon_max"]),
    )


def apply_bbox_to_session_state(session_state: MutableMapping[str, Any], source: str, bounds: LatLonBounds) -> None:
    prefix = _source_prefix(source)
    if source == SOURCE_SWISS:
        session_state["swiss_bbox_mode"] = "Geographischer Rahmen"
        session_state["swiss_lat_min"] = bounds.lat_min
        session_state["swiss_lon_min"] = bounds.lon_min
        session_state["swiss_lat_max"] = bounds.lat_max
        session_state["swiss_lon_max"] = bounds.lon_max
        session_state["swiss_center_lat"] = bounds.center_lat
        session_state["swiss_center_lon"] = bounds.center_lon
        return

    session_state[f"{prefix}_area_mode"] = "Geographischer Rahmen"
    session_state[f"{prefix}_lat_min"] = bounds.lat_min
    session_state[f"{prefix}_lon_min"] = bounds.lon_min
    session_state[f"{prefix}_lat_max"] = bounds.lat_max
    session_state[f"{prefix}_lon_max"] = bounds.lon_max
    session_state[f"{prefix}_lat"] = bounds.center_lat
    session_state[f"{prefix}_lon"] = bounds.center_lon


def apply_center_to_session_state(session_state: MutableMapping[str, Any], source: str, point: LatLonPoint) -> None:
    prefix = _source_prefix(source)
    if source == SOURCE_SWISS:
        session_state["swiss_bbox_mode"] = "GPS-Mittelpunkt"
        session_state["swiss_center_lat"] = point.lat
        session_state["swiss_center_lon"] = point.lon
        return

    session_state[f"{prefix}_area_mode"] = "GPS-Mittelpunkt"
    session_state[f"{prefix}_lat"] = point.lat
    session_state[f"{prefix}_lon"] = point.lon


def render_interactive_bbox_selector(source: str) -> None:
    try:
        import folium
    except Exception:
        st.info("Die Kartenvorschau ist nur mit installiertem `folium` verfuegbar.")
        return

    with st.expander("Interaktive Rechteckauswahl", expanded=False):
        picker_modes = ["Statische Vorschau", "Interaktive Auswahl"]
        if st.session_state.get("ui_bbox_picker_mode") not in picker_modes:
            st.session_state["ui_bbox_picker_mode"] = "Statische Vorschau"
        picker_mode = st.radio(
            "Kartenmodus",
            picker_modes,
            key="ui_bbox_picker_mode",
            horizontal=True,
            help="Statische Vorschau oder interaktive Auswahl.",
        )
        st.caption("Die interaktive Auswahl uebernimmt Punkte und Rahmen direkt.")
        center_lat, center_lon = current_source_center(st.session_state, source)
        current_bbox = current_source_bbox(st.session_state, source)
        picker_zoom = suggested_picker_zoom(st.session_state, source)

        map_object = folium.Map(location=[center_lat, center_lon], zoom_start=picker_zoom, tiles=None, control_scale=True)
        folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(map_object)
        folium.TileLayer(tiles=ESRI_TILE_URL, attr=ESRI_ATTRIBUTION, name="Esri Topo").add_to(map_object)
        if current_bbox is not None:
            folium.Rectangle(
                bounds=[[current_bbox.lat_min, current_bbox.lon_min], [current_bbox.lat_max, current_bbox.lon_max]],
                color="#1f77b4",
                weight=2,
                fill=False,
                tooltip="Aktueller Rahmen",
            ).add_to(map_object)
            map_object.fit_bounds([[current_bbox.lat_min, current_bbox.lon_min], [current_bbox.lat_max, current_bbox.lon_max]])

        folium.LayerControl(collapsed=True).add_to(map_object)

        if picker_mode == "Statische Vorschau":
            try:
                from streamlit_folium import folium_static

                folium_static(map_object, width=None, height=460)
            except Exception:
                st.components.v1.html(map_object._repr_html_(), height=500, scrolling=False)
            st.caption(f"Mittelpunkt: Lat {center_lat:.6f}, Lon {center_lon:.6f}")
            if current_bbox is not None:
                st.caption(
                    f"Rahmen: Lat {current_bbox.lat_min:.6f}..{current_bbox.lat_max:.6f}, "
                    f"Lon {current_bbox.lon_min:.6f}..{current_bbox.lon_max:.6f}"
                )
            st.info("Fuer Punkt- oder Rahmenselektion auf `Interaktive Auswahl` umstellen.")
            return

        reset_key = picker_reset_key(source)
        if reset_key not in st.session_state:
            st.session_state[reset_key] = 0
        component_value = render_leaflet_picker(
            center_lat=center_lat,
            center_lon=center_lon,
            zoom=picker_zoom,
            current_bbox=(
                {
                    "lat_min": current_bbox.lat_min,
                    "lon_min": current_bbox.lon_min,
                    "lat_max": current_bbox.lat_max,
                    "lon_max": current_bbox.lon_max,
                }
                if current_bbox is not None
                else None
            ),
            reset_token=int(st.session_state[reset_key]),
            key=f"leaflet_picker_{source}",
            height=460,
        )

        clicked_point = point_from_component_value(component_value)
        drawn_bounds = bounds_from_component_value(component_value)
        state_key = picker_state_key(source)
        point_state_key = picker_point_state_key(source)
        event_key = picker_event_key(source)
        selection_type = component_value.get("selection_type") if isinstance(component_value, Mapping) else None
        event_id = component_value.get("event_id") if isinstance(component_value, Mapping) else None

        if event_id is not None and event_id != st.session_state.get(event_key):
            st.session_state[event_key] = event_id
            if selection_type == "point" and clicked_point is not None:
                st.session_state[point_state_key] = {
                    "lat": clicked_point.lat,
                    "lon": clicked_point.lon,
                }
                st.session_state.pop(state_key, None)
            elif selection_type == "bounds" and drawn_bounds is not None:
                st.session_state[state_key] = {
                    "lat_min": drawn_bounds.lat_min,
                    "lon_min": drawn_bounds.lon_min,
                    "lat_max": drawn_bounds.lat_max,
                    "lon_max": drawn_bounds.lon_max,
                }
                st.session_state.pop(point_state_key, None)
            elif selection_type == "none":
                st.session_state.pop(point_state_key, None)
                st.session_state.pop(state_key, None)

        selected_point = st.session_state.get(point_state_key)
        if selected_point:
            point = LatLonPoint(lat=float(selected_point["lat"]), lon=float(selected_point["lon"]))
            st.caption(f"Ausgewaehlter Punkt: Lat {point.lat:.6f}, Lon {point.lon:.6f}")
            point_apply_col, point_clear_col = st.columns(2)
            if point_apply_col.button("Punkt als Mittelpunkt uebernehmen", key=f"apply_center_picker_{source}", use_container_width=True):
                apply_center_to_session_state(st.session_state, source, point)
                del st.session_state[point_state_key]
                st.session_state[reset_key] = int(st.session_state[reset_key]) + 1
                st.rerun()
            if point_clear_col.button("Punkt verwerfen", key=f"clear_center_picker_{source}", use_container_width=True):
                del st.session_state[point_state_key]
                st.session_state[reset_key] = int(st.session_state[reset_key]) + 1
                st.rerun()

        selected = st.session_state.get(state_key)
        if not selected:
            if not selected_point:
                st.caption("Auf die Karte klicken oder einen Rahmen ziehen.")
            return

        selected_bounds = LatLonBounds(
            lat_min=float(selected["lat_min"]),
            lon_min=float(selected["lon_min"]),
            lat_max=float(selected["lat_max"]),
            lon_max=float(selected["lon_max"]),
        )
        st.caption(
            f"Ausgewaehlter Rahmen: Lat {selected_bounds.lat_min:.6f}..{selected_bounds.lat_max:.6f}, "
            f"Lon {selected_bounds.lon_min:.6f}..{selected_bounds.lon_max:.6f}"
        )
        st.caption(
            f"Mittelpunkt: Lat {selected_bounds.center_lat:.6f}, "
            f"Lon {selected_bounds.center_lon:.6f}"
        )
        if source != SOURCE_SWISS:
            effective_selected_bounds = _effective_tile_source_bounds(st.session_state, source, selected_bounds)
            if effective_selected_bounds is not None:
                st.caption(
                    f"Effektiver Rahmen bei aktueller Detailstufe: "
                    f"Lat {effective_selected_bounds.lat_min:.6f}..{effective_selected_bounds.lat_max:.6f}, "
                    f"Lon {effective_selected_bounds.lon_min:.6f}..{effective_selected_bounds.lon_max:.6f}"
                )
        apply_col, clear_col = st.columns(2)
        if apply_col.button("Rechteck uebernehmen", key=f"apply_bbox_picker_{source}", use_container_width=True):
            apply_bbox_to_session_state(st.session_state, source, selected_bounds)
            del st.session_state[state_key]
            st.session_state[reset_key] = int(st.session_state[reset_key]) + 1
            st.rerun()
        if clear_col.button("Auswahl verwerfen", key=f"clear_bbox_picker_{source}", use_container_width=True):
            del st.session_state[state_key]
            st.session_state[reset_key] = int(st.session_state[reset_key]) + 1
            st.rerun()
