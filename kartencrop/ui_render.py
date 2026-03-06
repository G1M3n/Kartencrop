from __future__ import annotations

from pathlib import Path

import streamlit as st

from .capabilities import geopf_capabilities_source
from .geo import bbox_to_tile_bounds, latlon_to_tile, tile_bounds_to_geo_bounds
from .openaip_render import LAYER_COLORS
from .providers import (
    OFM_MAX_ZOOM,
    OFM_MIN_ZOOM,
    OPENAIP_MAX_ZOOM,
    OPENAIP_MIN_ZOOM,
    geopf_scan_oaci_limits,
)
from .swissgeo import (
    SWISS_CLOSURES_LAYER,
    SWISS_WMS_LAYER_PRESETS,
    SwissBoundingBox,
    bbox_from_center,
    bbox_from_wgs84_bounds,
    bbox_from_wgs84_center,
    dimensions_from_bbox_long_edge,
    merge_layers,
    parse_bbox,
    remove_layer,
    wgs84_to_lv95,
)
from .tiles import Bounds, clip_bounds
from .ui_models import GeoPfUIConfig, OfmUIConfig, OpenAipUIConfig, SwissUIConfig, UIConfig
from .ui_shared import (
    SOURCE_GEOPF,
    SOURCE_LABELS,
    SOURCE_OFM,
    SOURCE_OPENAIP,
    SOURCE_OPENAIP_COMPOSITE,
    SOURCE_OPENAIP_PNG,
    SOURCE_SWISS,
    current_bounds,
    adaptive_tile_radius,
    effective_bounds_label,
    nearest_preset_label,
    section_header,
    suggested_output_name,
    sync_zoom_scaled_state,
    warn_if_large_request,
)


SWISS_PRESET_LABELS = {
    "wanderkarte": "Wanderkarte (Farbkarte + Wanderwege)",
    "pixelkarte-farbe": "Topografische Farbkarte",
    "wanderwege": "Nur Wanderwege",
    "zeitreihe": "Zeitreihe",
    "custom": "Eigene Layer",
}

SWISS_AREA_PRESETS_KM = {
    "Sehr nah": 2,
    "Nah": 5,
    "Standard": 10,
    "Weit": 25,
    "Sehr weit": 50,
}

SWISS_OUTPUT_PRESETS = {
    "Kompakt": 1200,
    "Standard": 1800,
    "Hoch": 2600,
    "Sehr hoch": 3600,
}

SIMPLE_TILE_AREA_PRESETS = {
    "Sehr nah": 1,
    "Nah": 2,
    "Standard": 3,
    "Weit": 4,
    "Sehr weit": 5,
}

OFM_DETAIL_PRESETS = {
    "Uebersicht": 8,
    "Standard": 9,
    "Detail": 10,
    "Sehr detailreich": 11,
}

GEOPF_DETAIL_PRESETS = {
    "Uebersicht": 8,
    "Standard": 9,
    "Detail": 10,
    "Sehr detailreich": 11,
}

OPENAIP_DETAIL_PRESETS = {
    "Uebersicht": 7,
    "Standard": 9,
    "Detail": 11,
    "Sehr detailreich": 13,
}


def _ensure_valid_state_option(key: str, options: list[str], fallback: str | None = None) -> None:
    if st.session_state.get(key) not in options:
        st.session_state[key] = fallback if fallback in options else options[0]


def _render_preset_slider(
    *,
    label: str,
    state_key: str,
    preset_map: dict[str, int | float],
    target_value: int | float,
    help_text: str,
    caption_template: str | None = None,
    caption_builder=None,
    sync_to_target: bool = True,
) -> tuple[str, int | float]:
    sync_key = f"{state_key}__target"
    current_target = float(target_value)
    if (
        st.session_state.get(state_key) not in preset_map
        or (
            sync_to_target
            and float(st.session_state.get(sync_key, current_target)) != current_target
        )
    ):
        st.session_state[state_key] = nearest_preset_label(target_value, preset_map)
        st.session_state[sync_key] = current_target
    selected = st.select_slider(
        label,
        options=list(preset_map.keys()),
        key=state_key,
        help=help_text,
    )
    value = preset_map[selected]
    st.session_state[sync_key] = float(value)
    if caption_builder is not None:
        st.caption(caption_builder(selected, value))
    elif caption_template is not None:
        st.caption(caption_template.format(label=selected, value=value))
    return selected, value


def _clip_geopf_bounds(bounds: Bounds, tilematrix_level: int) -> Bounds | None:
    min_col, max_col, min_row, max_row = geopf_scan_oaci_limits()[int(tilematrix_level)]
    return clip_bounds(
        bounds,
        min_x=min_col,
        max_x=max_col,
        min_y=min_row,
        max_y=max_row,
    )


def render_ofm_config() -> OfmUIConfig:
    expert_mode = bool(st.session_state.get("ui_expert_mode", False))
    section_header("1. Karte", "Waehle den Kartenstil.")
    render_mode_options = ["Luftfahrtkarte (aero)", "Grundkarte (base)", "Grundkarte + Luftfahrtkarte"]
    _ensure_valid_state_option("ofm_render_mode_label", render_mode_options, "Luftfahrtkarte (aero)")
    render_mode_label = st.radio(
        "Darstellung",
        render_mode_options,
        key="ofm_render_mode_label",
        horizontal=True,
        help="`aero` ist transparent und eignet sich zum Ueberlagern. `base` ist die Grundkarte. Die Kombi legt `aero` auf `base`.",
    )
    chart_type = "aero" if render_mode_label == "Luftfahrtkarte (aero)" else "base"
    render_mode = "composite" if render_mode_label == "Grundkarte + Luftfahrtkarte" else "single"

    cycle = st.session_state.get("ofm_cycle", "latest")
    if expert_mode:
        with st.expander("Erweiterte OFM-Einstellungen", expanded=False):
            cycle = st.text_input(
                "Kartenzyklus",
                key="ofm_cycle",
                help="Normalerweise `latest`. Nur aendern, wenn du bewusst einen anderen OFM-Zyklus testen willst.",
            )

    section_header("2. Detail", "Im Anfaengermodus waehlst du nur eine grobe Detailstufe. Exakte Zoomwerte gibt es im Expertenmodus.")
    if expert_mode:
        zoom = st.number_input(
            "Zoomstufe",
            min_value=OFM_MIN_ZOOM,
            max_value=OFM_MAX_ZOOM,
            key="ofm_zoom",
            help=f"Der aktuell gepruefte OFM-Bereich liegt zwischen Zoom {OFM_MIN_ZOOM} und {OFM_MAX_ZOOM}.",
        )
        detail_label = f"Zoom {int(zoom)}"
    else:
        detail_label, zoom = _render_preset_slider(
            label="Detailstufe",
            state_key="ofm_detail_preset",
            preset_map=OFM_DETAIL_PRESETS,
            target_value=int(st.session_state.get("ofm_zoom", 8)),
            help_text="Hoehere Detailstufen laden kleinere Kartenausschnitte schaerfer und benoetigen mehr Tiles.",
            caption_template="Ausgewaehlt: {label} (entspricht Zoom {value}).",
        )
        st.session_state["ofm_zoom"] = int(zoom)
    sync_zoom_scaled_state(
        state_prefix="ofm",
        current_zoom=int(zoom),
        x_key="ofm_start_x",
        y_key="ofm_start_y",
        radius_keys=["ofm_max_search", "ofm_coverage_search"],
    )
    section_header("3. Bereich", "Waehle entweder einen Mittelpunkt oder einen geographischen Rahmen.")

    area_options = ["GPS-Mittelpunkt", "Geographischer Rahmen"]
    if expert_mode:
        area_options.extend(
            [
                "Zusammenhaengende OFM-Flaeche ab Start-Tile (technisch)",
                "Manueller Tile-Rahmen (technisch)",
            ]
        )
    _ensure_valid_state_option("ofm_area_mode", area_options, "GPS-Mittelpunkt")
    area_mode = st.radio(
        "Bereich laden ueber",
        area_options,
        key="ofm_area_mode",
        help="Fuer normale Nutzung sind GPS-Mittelpunkt oder geographischer Rahmen sinnvoll. Technische Tile-Modi erscheinen nur im Expertenmodus.",
    )
    coverage_search = int(st.session_state["ofm_coverage_search"])
    radius = int(st.session_state["ofm_max_search"])

    bounds = None
    area_text = ""
    area_strategy = "component"
    start_tile_x = int(st.session_state["ofm_start_x"])
    start_tile_y = int(st.session_state["ofm_start_y"])
    if area_mode == "Manueller Tile-Rahmen (technisch)":
        st.caption("Manuelle X/Y-Werte werden beim Zoomwechsel skaliert.")
        col1, col2 = st.columns(2)
        with col1:
            start_tile_x = st.number_input("Start-Tile X", min_value=0, key="ofm_start_x", help="Horizontale Tile-Koordinate des Startpunkts. Bewaehrter Anker fuer Zoom 8: X 144.")
        with col2:
            start_tile_y = st.number_input("Start-Tile Y", min_value=0, key="ofm_start_y", help="Vertikale Tile-Koordinate des Startpunkts. Bewaehrter Anker fuer Zoom 8: Y 72.")
        radius = st.number_input("Tile-Radius", min_value=0, key="ofm_max_search", help="Wert 2 bedeutet 5x5 Tiles.")
        bounds = current_bounds(int(start_tile_x), int(start_tile_y), int(radius))
        area_strategy = "bounds"
        area_text = f"Manueller Tile-Rahmen: {effective_bounds_label(bounds)}"
    elif area_mode == "GPS-Mittelpunkt":
        gps_col1, gps_col2 = st.columns(2)
        with gps_col1:
            lat = st.number_input("Breitengrad", format="%.6f", key="ofm_lat", help="GPS-Breitengrad des gewuenschten Mittelpunkts.")
        with gps_col2:
            lon = st.number_input("Laengengrad", format="%.6f", key="ofm_lon", help="GPS-Laengengrad des gewuenschten Mittelpunkts.")
        if expert_mode:
            radius = st.number_input("Radius um den Mittelpunkt (Tiles)", min_value=0, key="ofm_max_search", help="Wert 2 bedeutet 5x5 Tiles um den Mittelpunkt.")
        else:
            current_area_label = st.session_state.get("ofm_area_preset", "Nah")
            area_label, base_radius = _render_preset_slider(
                label="Ausschnitt um den Mittelpunkt",
                state_key="ofm_area_preset",
                preset_map=SIMPLE_TILE_AREA_PRESETS,
                target_value=SIMPLE_TILE_AREA_PRESETS.get(current_area_label, 2),
                help_text="Legt fest, wie gross der Tile-Ausschnitt um den Mittelpunkt sein soll.",
                sync_to_target=False,
            )
            radius = adaptive_tile_radius(
                base_radius=int(base_radius),
                detail_level=int(zoom),
                reference_level=OFM_DETAIL_PRESETS["Standard"],
                min_radius=1,
                max_radius=12,
            )
            st.session_state["ofm_max_search"] = radius
            st.caption(
                f"Ausgewaehlt: {area_label}. Bei {detail_label} ergibt das automatisch "
                f"Radius {radius} bzw. {2 * radius + 1}x{2 * radius + 1} Tiles."
            )
        tile = latlon_to_tile(float(lat), float(lon), int(zoom))
        bounds = current_bounds(tile.x, tile.y, int(radius))
        area_strategy = "bounds"
        start_tile_x = tile.x
        start_tile_y = tile.y
        area_text = f"GPS-Mittelpunkt {float(lat):.6f}, {float(lon):.6f} -> {effective_bounds_label(bounds)}"
        st.info(f"Berechneter OFM-Tile-Mittelpunkt fuer Zoom {tile.z}: X {tile.x}, Y {tile.y}")
    elif area_mode == "Geographischer Rahmen":
        bbox_col1, bbox_col2 = st.columns(2)
        with bbox_col1:
            lat_min = st.number_input("Breitengrad unten", format="%.6f", key="ofm_lat_min", help="Suedlicher Rand des Bereichs.")
            lat_max = st.number_input("Breitengrad oben", format="%.6f", key="ofm_lat_max", help="Noerdlicher Rand des Bereichs.")
        with bbox_col2:
            lon_min = st.number_input("Laengengrad links", format="%.6f", key="ofm_lon_min", help="Westlicher Rand des Bereichs.")
            lon_max = st.number_input("Laengengrad rechts", format="%.6f", key="ofm_lon_max", help="Oestlicher Rand des Bereichs.")
        tile_bounds = bbox_to_tile_bounds(float(lat_min), float(lon_min), float(lat_max), float(lon_max), int(zoom))
        effective_geo_bounds = tile_bounds_to_geo_bounds(tile_bounds)
        bounds = Bounds(tile_bounds.min_x, tile_bounds.max_x, tile_bounds.min_y, tile_bounds.max_y)
        area_strategy = "bounds"
        start_tile_x = tile_bounds.center_x
        start_tile_y = tile_bounds.center_y
        area_text = (
            "Geographischer Rahmen -> effektiv "
            f"Lat {effective_geo_bounds.lat_min:.4f}..{effective_geo_bounds.lat_max:.4f}, "
            f"Lon {effective_geo_bounds.lon_min:.4f}..{effective_geo_bounds.lon_max:.4f}"
        )
        st.info(
            f"Berechneter OFM-Tile-Bereich fuer Zoom {tile_bounds.z}: X {tile_bounds.min_x}..{tile_bounds.max_x}, "
            f"Y {tile_bounds.min_y}..{tile_bounds.max_y}"
        )
        st.caption(
            f"Angefragt: Lat {float(lat_min):.4f}..{float(lat_max):.4f}, "
            f"Lon {float(lon_min):.4f}..{float(lon_max):.4f}"
        )
        st.caption(
            f"Effektiv bei {detail_label}: Lat {effective_geo_bounds.lat_min:.4f}..{effective_geo_bounds.lat_max:.4f}, "
            f"Lon {effective_geo_bounds.lon_min:.4f}..{effective_geo_bounds.lon_max:.4f}"
        )
        st.caption(
            "OFM arbeitet mit ganzen Tiles. Der effektive Rahmen aendert sich daher mit der Detailstufe."
        )
    else:
        st.caption("Manuelle X/Y-Werte werden beim Zoomwechsel skaliert.")
        col1, col2 = st.columns(2)
        with col1:
            start_tile_x = st.number_input("Start-Tile X", min_value=0, key="ofm_start_x", help="Horizontale Tile-Koordinate des Startpunkts. Bewaehrter Anker fuer Zoom 8: X 144.")
        with col2:
            start_tile_y = st.number_input("Start-Tile Y", min_value=0, key="ofm_start_y", help="Vertikale Tile-Koordinate des Startpunkts. Bewaehrter Anker fuer Zoom 8: Y 72.")
        coverage_search = st.number_input(
            "Suchradius fuer Grenzerkennung",
            min_value=1,
            key="ofm_coverage_search",
            help="Je groesser der Wert, desto weiter wird die OFM-Abdeckung um den Startpunkt abgesucht.",
        )
        area_text = "Zusammenhaengende OFM-Flaeche um den Startpunkt."

    summary = [
        f"Darstellung: {render_mode_label}",
        f"Detail: {detail_label}",
        area_text,
    ]
    if expert_mode:
        summary.insert(2, f"Anker-Tile: X {start_tile_x}, Y {start_tile_y}")

    return OfmUIConfig(
        source=SOURCE_OFM,
        zoom=int(zoom),
        cycle=cycle,
        render_mode=render_mode,
        chart_type=chart_type,
        start_x=int(start_tile_x),
        start_y=int(start_tile_y),
        coverage_search=int(coverage_search),
        radius=int(radius),
        area_strategy=area_strategy,
        use_detected_range=area_mode == "Zusammenhaengende OFM-Flaeche ab Start-Tile (technisch)",
        bounds=bounds,
        summary=summary,
    )


def render_geopf_config() -> GeoPfUIConfig:
    expert_mode = bool(st.session_state.get("ui_expert_mode", False))
    geopf_limits = geopf_scan_oaci_limits()
    geopf_min_tilematrix = min(geopf_limits)
    geopf_max_tilematrix = max(geopf_limits)
    section_header("1. Karte", "GeoPF liefert die Frankreich-Karte ueber WMTS.")
    st.info("GPS und Rahmen werden automatisch auf die GeoPF-Abdeckung abgebildet.")
    section_header("2. Detail", "Im Anfaengermodus waehlst du nur eine grobe Detailstufe. Exakte TileMatrix-Werte gibt es im Expertenmodus.")
    if expert_mode:
        tilematrix_level = st.number_input(
            "TileMatrix",
            min_value=geopf_min_tilematrix,
            max_value=geopf_max_tilematrix,
            key="geopf_tilematrix",
            help=f"Aktueller SCAN-OACI-Bereich laut WMTS-Capabilities: {geopf_min_tilematrix} bis {geopf_max_tilematrix}.",
        )
        detail_label = f"TileMatrix {int(tilematrix_level)}"
    else:
        detail_label, tilematrix_level = _render_preset_slider(
            label="Detailstufe",
            state_key="geopf_detail_preset",
            preset_map=GEOPF_DETAIL_PRESETS,
            target_value=int(st.session_state.get("geopf_tilematrix", 11)),
            help_text="Hoehere Detailstufen nutzen feinere GeoPF-Tiles und vergroessern die Datenmenge.",
            caption_template="Ausgewaehlt: {label} (entspricht TileMatrix {value}).",
        )
        st.session_state["geopf_tilematrix"] = int(tilematrix_level)
    sync_zoom_scaled_state(
        state_prefix="geopf",
        current_zoom=int(tilematrix_level),
        x_key="geopf_start_col",
        y_key="geopf_start_row",
        radius_keys=["geopf_max_search", "geopf_coverage_search"],
        bounds_by_zoom=geopf_limits,
    )
    st.caption(f"GeoPF-Grenzen: {geopf_capabilities_source()}")
    min_col, max_col, min_row, max_row = geopf_limits[int(tilematrix_level)]
    st.caption(f"Gueltiger Bereich fuer TileMatrix {int(tilematrix_level)}: Spalte {min_col}..{max_col}, Zeile {min_row}..{max_row}")
    st.session_state["geopf_start_col"] = max(min_col, min(max_col, int(st.session_state["geopf_start_col"])))
    st.session_state["geopf_start_row"] = max(min_row, min(max_row, int(st.session_state["geopf_start_row"])))
    section_header("3. Bereich", "Waehle entweder einen Mittelpunkt oder einen geographischen Rahmen.")
    area_options = ["GPS-Mittelpunkt", "Geographischer Rahmen"]
    if expert_mode:
        area_options.extend(
            [
                "Gefundene Kartenflaeche ab Startpunkt (technisch)",
                "Manueller Tile-Rahmen (technisch)",
            ]
        )
    _ensure_valid_state_option("geopf_area_mode", area_options, "GPS-Mittelpunkt")
    area_mode = st.radio(
        "Bereich laden ueber",
        area_options,
        key="geopf_area_mode",
        help="Fuer normale Nutzung ist ein GPS-Mittelpunkt mit Radius am einfachsten. Technische Tile-Modi erscheinen nur im Expertenmodus.",
    )
    coverage_search = int(st.session_state["geopf_coverage_search"])
    radius = int(st.session_state["geopf_max_search"])

    bounds = None
    area_text = ""
    area_strategy = "component"
    start_col = int(st.session_state["geopf_start_col"])
    start_row = int(st.session_state["geopf_start_row"])

    if area_mode == "GPS-Mittelpunkt":
        col1, col2 = st.columns(2)
        with col1:
            lat = st.number_input("Breitengrad", format="%.6f", key="geopf_lat", help="GPS-Breitengrad des gewuenschten Mittelpunkts in Frankreich.")
        with col2:
            lon = st.number_input("Laengengrad", format="%.6f", key="geopf_lon", help="GPS-Laengengrad des gewuenschten Mittelpunkts in Frankreich.")
        if expert_mode:
            radius = st.number_input("Radius um den Mittelpunkt (Tiles)", min_value=0, key="geopf_max_search", help="Wert 2 bedeutet 5x5 Tiles um den Mittelpunkt.")
        else:
            current_area_label = st.session_state.get("geopf_area_preset", "Nah")
            area_label, base_radius = _render_preset_slider(
                label="Ausschnitt um den Mittelpunkt",
                state_key="geopf_area_preset",
                preset_map=SIMPLE_TILE_AREA_PRESETS,
                target_value=SIMPLE_TILE_AREA_PRESETS.get(current_area_label, 2),
                help_text="Legt fest, wie gross der Tile-Ausschnitt um den Mittelpunkt sein soll.",
                sync_to_target=False,
            )
            radius = adaptive_tile_radius(
                base_radius=int(base_radius),
                detail_level=int(tilematrix_level),
                reference_level=GEOPF_DETAIL_PRESETS["Standard"],
                min_radius=1,
                max_radius=12,
            )
            st.session_state["geopf_max_search"] = radius
            st.caption(
                f"Ausgewaehlt: {area_label}. Bei {detail_label} ergibt das automatisch "
                f"Radius {radius} bzw. {2 * radius + 1}x{2 * radius + 1} Tiles."
            )
        tile = latlon_to_tile(float(lat), float(lon), int(tilematrix_level))
        raw_bounds = current_bounds(tile.x, tile.y, int(radius))
        bounds = _clip_geopf_bounds(raw_bounds, int(tilematrix_level))
        area_strategy = "bounds"
        start_col = tile.x
        start_row = tile.y
        if bounds is None:
            st.error("Der gewaehlte Mittelpunkt liegt ausserhalb der verfuegbaren GeoPF-Frankreich-Abdeckung in dieser TileMatrix.")
            area_text = "GPS-Mittelpunkt ausserhalb der GeoPF-Abdeckung."
        else:
            area_text = f"GPS-Mittelpunkt {float(lat):.6f}, {float(lon):.6f} -> Spalten {bounds.min_x}..{bounds.max_x}, Zeilen {bounds.min_y}..{bounds.max_y}"
            st.info(f"Berechneter Mittelpunkt fuer TileMatrix {int(tilematrix_level)}: Spalte {tile.x}, Zeile {tile.y}")
            if bounds != raw_bounds:
                st.warning("Der Bereich wurde auf die gueltige Frankreich-Abdeckung beschnitten.")
    elif area_mode == "Geographischer Rahmen":
        col1, col2 = st.columns(2)
        with col1:
            lat_min = st.number_input("Breitengrad unten", format="%.6f", key="geopf_lat_min", help="Suedlicher Rand des Bereichs.")
            lat_max = st.number_input("Breitengrad oben", format="%.6f", key="geopf_lat_max", help="Noerdlicher Rand des Bereichs.")
        with col2:
            lon_min = st.number_input("Laengengrad links", format="%.6f", key="geopf_lon_min", help="Westlicher Rand des Bereichs.")
            lon_max = st.number_input("Laengengrad rechts", format="%.6f", key="geopf_lon_max", help="Oestlicher Rand des Bereichs.")
        tile_bounds = bbox_to_tile_bounds(float(lat_min), float(lon_min), float(lat_max), float(lon_max), int(tilematrix_level))
        raw_bounds = Bounds(tile_bounds.min_x, tile_bounds.max_x, tile_bounds.min_y, tile_bounds.max_y)
        bounds = _clip_geopf_bounds(raw_bounds, int(tilematrix_level))
        area_strategy = "bounds"
        start_col = tile_bounds.center_x
        start_row = tile_bounds.center_y
        if bounds is None:
            st.error("Der geographische Rahmen liegt komplett ausserhalb der verfuegbaren GeoPF-Frankreich-Abdeckung in dieser TileMatrix.")
            area_text = "Geographischer Rahmen ausserhalb der GeoPF-Abdeckung."
        else:
            area_text = f"Geographischer Rahmen: Spalten {bounds.min_x}..{bounds.max_x}, Zeilen {bounds.min_y}..{bounds.max_y}"
            st.info(
                f"Berechneter GeoPF-Bereich fuer TileMatrix {tile_bounds.z}: Spalten {tile_bounds.min_x}..{tile_bounds.max_x}, "
                f"Zeilen {tile_bounds.min_y}..{tile_bounds.max_y}"
            )
            if bounds != raw_bounds:
                st.warning("Der Rahmen lag teilweise ausserhalb der GeoPF-Abdeckung und wurde beschnitten.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            start_col = st.number_input("Start-Spalte", min_value=min_col, max_value=max_col, key="geopf_start_col", help="WMTS-Spalte des Startpunkts innerhalb des SCAN-OACI-Bereichs.")
        with col2:
            start_row = st.number_input("Start-Zeile", min_value=min_row, max_value=max_row, key="geopf_start_row", help="WMTS-Zeile des Startpunkts innerhalb des SCAN-OACI-Bereichs.")
        if area_mode == "Manueller Tile-Rahmen (technisch)":
            radius = st.number_input("Tile-Radius", min_value=0, key="geopf_max_search", help="Wert 2 bedeutet 5x5 Tiles.")
            bounds = current_bounds(int(start_col), int(start_row), int(radius))
            bounds = _clip_geopf_bounds(bounds, int(tilematrix_level))
            area_strategy = "bounds"
            area_text = (
                f"Manueller Rahmen: Spalte {bounds.min_x}..{bounds.max_x}, Zeile {bounds.min_y}..{bounds.max_y}"
                if bounds is not None
                else "Manueller Rahmen ausserhalb der GeoPF-Abdeckung."
            )
        else:
            coverage_search = st.number_input(
                "Suchradius fuer Grenzerkennung",
                min_value=1,
                key="geopf_coverage_search",
                help="Je groesser der Wert, desto weiter wird die GeoPF-Abdeckung um den Startpunkt abgesucht.",
            )
            area_text = "Gefundene GeoPF-Flaeche um den Startpunkt."

    summary = [
        f"Detail: {detail_label}",
        area_text,
    ]
    if expert_mode:
        summary.insert(1, f"Startpunkt: Spalte {int(start_col)}, Zeile {int(start_row)}")

    return GeoPfUIConfig(
        source=SOURCE_GEOPF,
        tilematrix=str(int(tilematrix_level)),
        start_x=int(start_col),
        start_y=int(start_row),
        coverage_search=int(coverage_search),
        radius=int(radius),
        area_strategy=area_strategy,
        use_detected_range=area_mode == "Gefundene Kartenflaeche ab Startpunkt (technisch)",
        bounds=bounds,
        summary=summary,
    )


def render_swiss_config() -> SwissUIConfig:
    expert_mode = bool(st.session_state.get("ui_expert_mode", False))
    section_header("1. Karte", "Waehle die Schweizer Grundkarte.")
    preset_options = ["wanderkarte", "pixelkarte-farbe", "wanderwege", "zeitreihe", "custom"]
    _ensure_valid_state_option("swiss_preset", preset_options, "wanderkarte")
    preset = st.selectbox(
        "Kartenvorlage",
        preset_options,
        key="swiss_preset",
        format_func=lambda value: SWISS_PRESET_LABELS[value],
        help="Vorlagen fuer die haeufigsten Kartenkombinationen. Fuer spezielle Layer auf `Eigene Layer` wechseln.",
    )
    if preset == "custom":
        base_layers = st.text_input("Layer-Liste", key="swiss_custom_layers", help="Kommagetrennte GeoAdmin-Layer.")
        if not base_layers:
            base_layers = SWISS_WMS_LAYER_PRESETS["wanderkarte"]
    else:
        base_layers = SWISS_WMS_LAYER_PRESETS[preset]
        st.caption(f"Aktive Grundlayer: {base_layers}")

    include_closures = st.checkbox(
        "Sperrungen und Umleitungen einblenden",
        key="swiss_include_closures",
        help="Blendet den offiziellen ASTRA-Layer fuer Wanderwegsperrungen und Umleitungen ein.",
    )
    if include_closures:
        effective_layers = merge_layers(remove_layer(base_layers, SWISS_CLOSURES_LAYER), SWISS_CLOSURES_LAYER)
    else:
        effective_layers = remove_layer(base_layers, SWISS_CLOSURES_LAYER)

    section_header("2. Bereich", "Waehle entweder einen Mittelpunkt oder einen geographischen Rahmen.")
    bbox_modes = ["GPS-Mittelpunkt", "Geographischer Rahmen"]
    if expert_mode:
        bbox_modes.extend(["LV95-Mittelpunkt (technisch)", "LV95-Bounding-Box (technisch)"])
    _ensure_valid_state_option("swiss_bbox_mode", bbox_modes, "GPS-Mittelpunkt")
    bbox_mode = st.radio(
        "Bereich angeben ueber",
        bbox_modes,
        key="swiss_bbox_mode",
        help="Fuer normale Nutzung sind GPS-Mittelpunkt oder geographischer Rahmen sinnvoll. LV95-Varianten erscheinen nur im Expertenmodus.",
    )
    bbox: SwissBoundingBox | None = None
    center_text = ""
    if bbox_mode == "GPS-Mittelpunkt":
        col1, col2 = st.columns(2)
        with col1:
            center_lat = st.number_input("Breitengrad", key="swiss_center_lat", format="%.6f", help="GPS-Breitengrad des Kartenmittelpunkts.")
        with col2:
            center_lon = st.number_input("Laengengrad", key="swiss_center_lon", format="%.6f", help="GPS-Laengengrad des Kartenmittelpunkts.")
        if expert_mode:
            size_col1, size_col2 = st.columns(2)
            with size_col1:
                span_x = st.number_input("Breite in Metern", min_value=1.0, key="swiss_span_x", format="%.2f", help="Reale Breite des Kartenausschnitts.")
            with size_col2:
                span_y = st.number_input("Hoehe in Metern", min_value=1.0, key="swiss_span_y", format="%.2f", help="Reale Hoehe des Kartenausschnitts.")
        else:
            if st.session_state.get("swiss_area_preset") not in SWISS_AREA_PRESETS_KM:
                st.session_state["swiss_area_preset"] = nearest_preset_label(
                    float(st.session_state.get("swiss_area_km", 10)),
                    SWISS_AREA_PRESETS_KM,
                )
            area_label = st.select_slider(
                "Ausschnitt um den Mittelpunkt",
                options=list(SWISS_AREA_PRESETS_KM.keys()),
                key="swiss_area_preset",
                help="Legt fest, wie gross der quadratische Kartenausschnitt um den Mittelpunkt sein soll.",
            )
            area_km = SWISS_AREA_PRESETS_KM[area_label]
            st.session_state["swiss_area_km"] = area_km
            span_x = float(area_km) * 1000.0
            span_y = float(area_km) * 1000.0
            st.caption(f"Ausgewaehlt: {area_label} ({float(area_km):.0f} km x {float(area_km):.0f} km).")
        lv95_x, lv95_y = wgs84_to_lv95(float(center_lat), float(center_lon))
        bbox = bbox_from_wgs84_center(float(center_lat), float(center_lon), float(span_x), float(span_y))
        center_text = f"GPS {float(center_lat):.6f}, {float(center_lon):.6f} -> LV95 {lv95_x:.2f}, {lv95_y:.2f}"
    elif bbox_mode == "Geographischer Rahmen":
        col1, col2 = st.columns(2)
        with col1:
            lat_min = st.number_input("Breitengrad unten", key="swiss_lat_min", format="%.6f", help="Suedlicher Rand des Bereichs.")
            lat_max = st.number_input("Breitengrad oben", key="swiss_lat_max", format="%.6f", help="Noerdlicher Rand des Bereichs.")
        with col2:
            lon_min = st.number_input("Laengengrad links", key="swiss_lon_min", format="%.6f", help="Westlicher Rand des Bereichs.")
            lon_max = st.number_input("Laengengrad rechts", key="swiss_lon_max", format="%.6f", help="Oestlicher Rand des Bereichs.")
        try:
            bbox = bbox_from_wgs84_bounds(float(lat_min), float(lon_min), float(lat_max), float(lon_max))
            center_text = f"Rahmen aus GPS-Koordinaten -> Mittelpunkt LV95 {bbox.center_x:.2f}, {bbox.center_y:.2f}"
        except ValueError as exc:
            st.error(str(exc))
            bbox = None
    elif bbox_mode == "LV95-Mittelpunkt (technisch)":
        col1, col2 = st.columns(2)
        with col1:
            center_x = st.number_input("Zentrum Ost (LV95)", key="swiss_center_x", format="%.2f", help="Ostwert des Kartenmittelpunkts in EPSG:2056 / LV95.")
            span_x = st.number_input("Breite in Metern", min_value=1.0, key="swiss_span_x", format="%.2f", help="Reale Breite des Kartenausschnitts.")
        with col2:
            center_y = st.number_input("Zentrum Nord (LV95)", key="swiss_center_y", format="%.2f", help="Nordwert des Kartenmittelpunkts in EPSG:2056 / LV95.")
            span_y = st.number_input("Hoehe in Metern", min_value=1.0, key="swiss_span_y", format="%.2f", help="Reale Hoehe des Kartenausschnitts.")
        bbox = bbox_from_center(float(center_x), float(center_y), float(span_x), float(span_y))
        center_text = f"LV95-Mittelpunkt: {float(center_x):.2f}, {float(center_y):.2f}"
    else:
        bbox_text = st.text_input("Bounding-Box", key="swiss_bbox_text", help="Format: min_x,min_y,max_x,max_y in EPSG:2056 / LV95.")
        try:
            bbox = parse_bbox(bbox_text)
            center_text = f"Mittelpunkt aus Bounding-Box: {bbox.center_x:.2f}, {bbox.center_y:.2f}"
        except ValueError as exc:
            st.error(str(exc))
            bbox = None

    if bbox is not None:
        st.info(f"Aktuelle Bounding-Box: {bbox.as_wms_bbox()} | {center_text}")

    section_header("3. Ausgabe", "Groesse und Format des fertigen Kartenbilds.")
    if expert_mode:
        col1, col2 = st.columns(2)
        with col1:
            output_width = st.number_input("Bildbreite in Pixel", min_value=64, step=64, key="swiss_output_width", help="Zielbreite des serverseitig gerenderten WMS-Bilds.")
            _ensure_valid_state_option("swiss_image_format", ["image/png", "image/jpeg"], "image/png")
            image_format = st.selectbox("Bildformat", ["image/png", "image/jpeg"], key="swiss_image_format", help="PNG ist fuer Beschriftungen und transparente Layer meist die bessere Wahl.")
        with col2:
            output_height = st.number_input("Bildhoehe in Pixel", min_value=64, step=64, key="swiss_output_height", help="Zielhoehe des serverseitig gerenderten WMS-Bilds.")
            if image_format == "image/png":
                transparent = st.checkbox("Transparenter Hintergrund", key="swiss_transparent", help="Fuer Overlay-Layer sinnvoll. Bei JPEG ist Transparenz technisch nicht moeglich.")
            else:
                transparent = False
                st.caption("JPEG unterstuetzt keine Transparenz.")
    else:
        _ensure_valid_state_option("swiss_quality_preset", list(SWISS_OUTPUT_PRESETS.keys()), "Standard")
        quality_preset = st.select_slider(
            "Ausgabequalitaet",
            options=list(SWISS_OUTPUT_PRESETS.keys()),
            key="swiss_quality_preset",
            help="Hoehere Qualitaet erzeugt ein groesseres Bild und braucht mehr Zeit und Speicher.",
        )
        _ensure_valid_state_option("swiss_image_format", ["image/png", "image/jpeg"], "image/png")
        image_format = st.selectbox("Bildformat", ["image/png", "image/jpeg"], key="swiss_image_format", help="PNG ist fuer Kartenbeschriftungen meist die bessere Wahl.")
        target_long_edge = SWISS_OUTPUT_PRESETS[quality_preset]
        if bbox is not None:
            output_width, output_height = dimensions_from_bbox_long_edge(bbox, target_long_edge)
        else:
            output_width, output_height = target_long_edge, target_long_edge
        transparent = image_format == "image/png"
        st.caption(f"Ergibt ungefaehr {int(output_width)} x {int(output_height)} Pixel.")
    if bbox is not None:
        st.caption(
            f"Effektive Aufloesung: {bbox.width_m / int(output_width):.2f} m/px horizontal, "
            f"{bbox.height_m / int(output_height):.2f} m/px vertikal."
        )

    identify_closures = False
    identify_tolerance = 12
    time_value: str | None = None
    styles = ""
    if expert_mode:
        with st.expander("Erweiterte Schweizer Optionen", expanded=False):
            st.caption("Zusatzoptionen fuer Zeitreihen, Styles und technische Detailabfragen.")
            time_value = st.text_input(
                "Zeitwert (optional)",
                key="swiss_time",
                help="Nur fuer Zeitreihen-Layer noetig. Beispiel: `1864` fuer historische Darstellungen.",
            ) or None
            styles = st.text_input(
                "Styles (optional)",
                key="swiss_styles",
                help="Nur verwenden, wenn du einen konkreten WMS-Style kennst. Im Normalfall leer lassen.",
            )
            identify_closures = st.checkbox(
                "Sperrungsdetails am Mittelpunkt abfragen",
                key="swiss_identify_closures",
                help="Fragt ueber die GeoAdmin-REST-API Zusatzinformationen zu Sperrungen am Kartenmittelpunkt ab. Das ist eine technische Zusatzabfrage, nicht der normale Kartenrender.",
            )
            if identify_closures:
                identify_tolerance = st.slider(
                    "Treffer-Toleranz in Pixel",
                    min_value=0,
                    max_value=30,
                    key="swiss_identify_tolerance",
                    help="Groessere Werte vergroessern den Suchbereich um den Mittelpunkt der Karte.",
                )

    if not effective_layers:
        st.error("Es ist kein Schweizer Layer aktiv.")
    summary = [
        f"Layer: {effective_layers or '-'}",
        f"Bereich: {bbox.as_wms_bbox() if bbox is not None else 'ungueltig'}",
        f"Bildgroesse: {int(output_width)}x{int(output_height)} Pixel",
    ]
    if include_closures:
        summary.append("Sperrungen: eingeblendet")
    if bbox_mode == "GPS-Mittelpunkt":
        summary.append(center_text)

    return SwissUIConfig(
        source=SOURCE_SWISS,
        layers=effective_layers,
        bbox=bbox,
        output_width=int(output_width),
        output_height=int(output_height),
        image_format=image_format,
        transparent=transparent,
        time=time_value,
        styles=styles,
        identify_closures=identify_closures,
        identify_tolerance=int(identify_tolerance),
        summary=summary,
    )


def render_openaip_config(source: str) -> OpenAipUIConfig:
    expert_mode = bool(st.session_state.get("ui_expert_mode", False))
    state_prefix = SOURCE_OPENAIP if source in {SOURCE_OPENAIP, SOURCE_OPENAIP_PNG, SOURCE_OPENAIP_COMPOSITE} else source
    section_header("1. Karte", "OpenAIP benoetigt einen API-Schluessel. Danach waehlst du den Layer.")
    api_key = st.text_input("OpenAIP API-Schluessel", key="openaip_api_key", type="password", help="Wird fuer OpenAIP Raster und Composite verwendet und in dieser Sitzung gespeichert.")
    st.caption(f"API-Schluessel gespeichert: {'ja' if st.session_state.openaip_api_key else 'nein'}")
    internal_source = source
    display_mode = ""
    if source == SOURCE_OPENAIP:
        _ensure_valid_state_option("openaip_display_mode", ["Nur OpenAIP", "OpenAIP mit Regionskarte"], "Nur OpenAIP")
        display_mode = st.radio(
            "Darstellung",
            ["Nur OpenAIP", "OpenAIP mit Regionskarte"],
            key="openaip_display_mode",
            help="`Nur OpenAIP` zeigt nur die OpenAIP-Karte. `OpenAIP mit Regionskarte` legt sie auf eine Hintergrundkarte.",
        )
        internal_source = SOURCE_OPENAIP_PNG if display_mode == "Nur OpenAIP" else SOURCE_OPENAIP_COMPOSITE
    layer = "openaip"
    if expert_mode:
        layer_options = ["openaip", "hotspots"]
        _ensure_valid_state_option("openaip_layer", layer_options, "openaip")
        layer = st.selectbox("OpenAIP-Layer", layer_options, key="openaip_layer", help="`openaip` ist die normale Karte, `hotspots` ist ein alternativer Raster-Layer.")

    basemap = "World_Topo_Map"
    overlay_alpha = 220
    white_threshold = 248
    if internal_source == SOURCE_OPENAIP_COMPOSITE:
        if expert_mode:
            basemap_options = ["World_Topo_Map", "World_Imagery"]
            _ensure_valid_state_option("openaip_basemap", basemap_options, "World_Topo_Map")
            basemap = st.selectbox("Regionskarte darunter", basemap_options, key="openaip_basemap", help="Topografische oder Satelliten-Basiskarte fuer das OpenAIP-Overlay.")
            with st.expander("Overlay-Abstimmung", expanded=False):
                overlay_alpha = st.slider("Deckkraft des OpenAIP-Overlays", min_value=50, max_value=255, key="openaip_overlay_alpha", help="Hoehere Werte machen die OpenAIP-Daten sichtbarer.")
                white_threshold = st.slider("Weiss als transparent behandeln ab", min_value=230, max_value=255, key="openaip_white_threshold", help="Helle Flaechen des Overlays werden ab diesem Wert entfernt, damit die Regionskarte sichtbar bleibt.")

    section_header("2. Detail", "Im Anfaengermodus waehlst du nur eine grobe Detailstufe. Exakte Zoomwerte gibt es im Expertenmodus.")
    if expert_mode:
        zoom = st.number_input(
            "Zoomstufe",
            min_value=OPENAIP_MIN_ZOOM,
            max_value=OPENAIP_MAX_ZOOM,
            key=f"{state_prefix}_zoom",
            help=f"Die Tile-Berechnung haengt direkt von dieser Zoomstufe ab. Live geprueft bis Zoom {OPENAIP_MAX_ZOOM}.",
        )
        detail_label = f"Zoom {int(zoom)}"
    else:
        detail_label, zoom = _render_preset_slider(
            label="Detailstufe",
            state_key=f"{state_prefix}_detail_preset",
            preset_map=OPENAIP_DETAIL_PRESETS,
            target_value=int(st.session_state.get(f"{state_prefix}_zoom", 9)),
            help_text="Hoehere Detailstufen nutzen feinere OpenAIP-Tiles und vergroessern die Datenmenge.",
            caption_template="Ausgewaehlt: {label} (entspricht Zoom {value}).",
        )
        st.session_state[f"{state_prefix}_zoom"] = int(zoom)
    section_header("3. Bereich", "Waehle entweder einen Mittelpunkt oder einen geographischen Rahmen.")
    area_options = ["GPS-Mittelpunkt", "Geographischer Rahmen"]
    if expert_mode:
        area_options.append("Tile-Koordinaten (manuell)")
    _ensure_valid_state_option(f"{state_prefix}_area_mode", area_options, "GPS-Mittelpunkt")
    area_mode = st.radio("Bereich angeben ueber", area_options, key=f"{state_prefix}_area_mode", help="Waehlst du GPS oder Rahmen, werden die Tiles automatisch fuer den aktuellen Zoom berechnet. Tile-Koordinaten erscheinen nur im Expertenmodus.")
    bounds: Bounds
    anchor_text: str
    if area_mode == "GPS-Mittelpunkt":
        col1, col2 = st.columns(2)
        with col1:
            lat = st.number_input("Breitengrad", key=f"{state_prefix}_lat", format="%.6f", help="GPS-Breitengrad des Mittelpunkts.")
        with col2:
            lon = st.number_input("Laengengrad", key=f"{state_prefix}_lon", format="%.6f", help="GPS-Laengengrad des Mittelpunkts.")
        if expert_mode:
            radius = st.number_input("Radius um den Mittelpunkt (Tiles)", min_value=0, key=f"{state_prefix}_radius", help="Wert 2 bedeutet 5x5 Tiles um die berechnete Mittel-Tile.")
        else:
            current_area_label = st.session_state.get(f"{state_prefix}_area_preset", "Nah")
            area_label, base_radius = _render_preset_slider(
                label="Ausschnitt um den Mittelpunkt",
                state_key=f"{state_prefix}_area_preset",
                preset_map=SIMPLE_TILE_AREA_PRESETS,
                target_value=SIMPLE_TILE_AREA_PRESETS.get(current_area_label, 2),
                help_text="Legt fest, wie gross der Tile-Ausschnitt um den Mittelpunkt sein soll.",
                sync_to_target=False,
            )
            radius = adaptive_tile_radius(
                base_radius=int(base_radius),
                detail_level=int(zoom),
                reference_level=OPENAIP_DETAIL_PRESETS["Standard"],
                min_radius=1,
                max_radius=14,
            )
            st.session_state[f"{state_prefix}_radius"] = radius
            st.caption(
                f"Ausgewaehlt: {area_label}. Bei {detail_label} ergibt das automatisch "
                f"Radius {radius} bzw. {2 * radius + 1}x{2 * radius + 1} Tiles."
            )
        tile = latlon_to_tile(float(lat), float(lon), int(zoom))
        bounds = current_bounds(tile.x, tile.y, int(radius))
        anchor_text = f"GPS {float(lat):.6f}, {float(lon):.6f} -> Tile X {tile.x}, Y {tile.y}"
        st.info(f"Berechneter Mittelpunkt fuer Zoom {tile.z}: X {tile.x}, Y {tile.y}")
    elif area_mode == "Geographischer Rahmen":
        col1, col2 = st.columns(2)
        with col1:
            lat_min = st.number_input("Breitengrad unten", key=f"{state_prefix}_lat_min", format="%.6f", help="Suedlicher Rand des Bereichs.")
            lat_max = st.number_input("Breitengrad oben", key=f"{state_prefix}_lat_max", format="%.6f", help="Noerdlicher Rand des Bereichs.")
        with col2:
            lon_min = st.number_input("Laengengrad links", key=f"{state_prefix}_lon_min", format="%.6f", help="Westlicher Rand des Bereichs.")
            lon_max = st.number_input("Laengengrad rechts", key=f"{state_prefix}_lon_max", format="%.6f", help="Oestlicher Rand des Bereichs.")
        tile_bounds = bbox_to_tile_bounds(float(lat_min), float(lon_min), float(lat_max), float(lon_max), int(zoom))
        bounds = Bounds(tile_bounds.min_x, tile_bounds.max_x, tile_bounds.min_y, tile_bounds.max_y)
        anchor_text = f"Geographischer Rahmen -> X {tile_bounds.min_x}..{tile_bounds.max_x}, Y {tile_bounds.min_y}..{tile_bounds.max_y}"
        st.info(f"Berechneter Tile-Bereich fuer Zoom {tile_bounds.z}: X {tile_bounds.min_x}..{tile_bounds.max_x}, Y {tile_bounds.min_y}..{tile_bounds.max_y}")
    else:
        col1, col2 = st.columns(2)
        with col1:
            tile_x = st.number_input("Start-Tile X", min_value=0, key=f"{state_prefix}_tile_x", help="Horizontale XYZ-Koordinate der Mittel-Tile.")
        with col2:
            tile_y = st.number_input("Start-Tile Y", min_value=0, key=f"{state_prefix}_tile_y", help="Vertikale XYZ-Koordinate der Mittel-Tile.")
        radius = st.number_input("Radius um den Mittelpunkt (Tiles)", min_value=0, key=f"{state_prefix}_radius", help="Wert 2 bedeutet 5x5 Tiles.")
        bounds = current_bounds(int(tile_x), int(tile_y), int(radius))
        anchor_text = f"Manueller Tile-Mittelpunkt: X {int(tile_x)}, Y {int(tile_y)}"

    render_vector_debug = False
    enabled_layers: list[str] = []
    if expert_mode:
        with st.expander("Erweiterte OpenAIP-Diagnose", expanded=False):
            st.caption("Optionaler Debug-Render der Vektordaten.")
            render_vector_debug = st.checkbox("Zusaetzliche Vektor-Diagnose speichern", key="openaip_render_vector_debug", help="Erzeugt zusaetzlich ein Debug-Bild der OpenAIP-Vektordaten im gewaehlten Bereich.")
            if render_vector_debug:
                if not st.session_state.get("openaip_enabled_layers"):
                    st.session_state["openaip_enabled_layers"] = list(LAYER_COLORS.keys())
                enabled_layers = st.multiselect("Vektor-Layer fuer die Diagnose", list(LAYER_COLORS.keys()), key="openaip_enabled_layers", help="Nur fuer die Diagnose relevant.")

    summary = [f"Detail: {detail_label}", f"Bereich: {effective_bounds_label(bounds)}"]
    if source == SOURCE_OPENAIP:
        summary.insert(0, f"Darstellung: {display_mode}")
    if expert_mode:
        summary.insert(1 if source == SOURCE_OPENAIP else 0, f"Layer: {layer}")
    if expert_mode or area_mode == "Tile-Koordinaten (manuell)":
        insert_at = 3 if source == SOURCE_OPENAIP else 2
        summary.insert(insert_at, anchor_text)
    if internal_source == SOURCE_OPENAIP_COMPOSITE:
        summary.append(f"Regionskarte: {basemap}")
    return OpenAipUIConfig(
        source=internal_source,
        api_key=api_key or None,
        layer=layer,
        zoom=int(zoom),
        bounds=bounds,
        basemap=basemap,
        overlay_alpha=int(overlay_alpha),
        white_threshold=int(white_threshold),
        render_vector_debug=render_vector_debug,
        enabled_layers=enabled_layers,
        summary=summary,
    )


def render_source_configuration(source: str) -> UIConfig:
    if source == SOURCE_OFM:
        return render_ofm_config()
    if source == SOURCE_GEOPF:
        return render_geopf_config()
    if source == SOURCE_SWISS:
        return render_swiss_config()
    if source in {SOURCE_OPENAIP, SOURCE_OPENAIP_PNG, SOURCE_OPENAIP_COMPOSITE}:
        return render_openaip_config(source)
    return render_openaip_config(source)


def render_summary(config: UIConfig, output_path: Path) -> None:
    st.subheader("Zusammenfassung")
    for line in config.summary:
        st.write(f"- {line}")
    st.write(f"- Ausgabeordner: {Path(st.session_state.output_directory).expanduser()}")
    st.write(f"- Zieldatei: {output_path.name}")
    st.code(str(output_path))
    warn_if_large_request(config)


def prepare_output_name(config: UIConfig) -> str:
    return suggested_output_name(config)


def page_title(source: str) -> str:
    return SOURCE_LABELS[source]
