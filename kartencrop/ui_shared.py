from __future__ import annotations

from copy import deepcopy
import math
from pathlib import Path

import streamlit as st
from PIL import Image

from .ui_persistence import clear_persisted_ui_state, load_persisted_ui_state, should_persist_ui_key
from .ui_models import GeoPfUIConfig, OfmUIConfig, OpenAipUIConfig, SwissUIConfig, UIConfig
from .providers import (
    GEOPF_MAX_TILEMATRIX,
    GEOPF_MIN_TILEMATRIX,
    OFM_MAX_ZOOM,
    OFM_MIN_ZOOM,
    OPENAIP_MAX_ZOOM,
)
from .swissgeo import SWISS_CLOSURES_LAYER
from .tiles import Bounds, find_bounds


SOURCE_OFM = "ofm"
SOURCE_GEOPF = "geopf"
SOURCE_SWISS = "swiss_wms"
SOURCE_OPENAIP = "openaip"
SOURCE_OPENAIP_PNG = "openaip_png"
SOURCE_OPENAIP_COMPOSITE = "openaip_composite"

SOURCE_LABELS = {
    SOURCE_OFM: "OpenFlightMaps (regional, Europa)",
    SOURCE_GEOPF: "GeoPF Frankreich",
    SOURCE_SWISS: "Schweizer Wanderkarte (GeoAdmin WMS)",
    SOURCE_OPENAIP: "OpenAIP",
    SOURCE_OPENAIP_PNG: "OpenAIP Raster",
    SOURCE_OPENAIP_COMPOSITE: "OpenAIP mit Regionskarte",
}

UI_STATE_DEFAULTS = {
    "ui_source": SOURCE_OFM,
    "ui_bbox_picker_mode": "Statische Vorschau",
    "openaip_api_key": "",
    "output_directory": str(Path.cwd() / "outputs" / "generated"),
    "ui_expert_mode": False,
    "ofm_render_mode_label": "Luftfahrtkarte (aero)",
    "ofm_area_mode": "GPS-Mittelpunkt",
    "ofm_last_zoom": 8,
    "ofm_zoom": 8,
    "ofm_start_x": 137,
    "ofm_start_y": 83,
    "ofm_max_search": 2,
    "ofm_coverage_search": 10,
    "ofm_detail_preset": "Uebersicht",
    "ofm_area_preset": "Nah",
    "ofm_cycle": "latest",
    "ofm_lat": 52.5200,
    "ofm_lon": 13.4050,
    "ofm_lat_min": 35.0,
    "ofm_lon_min": -10.0,
    "ofm_lat_max": 62.0,
    "ofm_lon_max": 25.0,
    "geopf_area_mode": "GPS-Mittelpunkt",
    "geopf_last_zoom": 11,
    "geopf_tilematrix": 11,
    "geopf_start_col": 1037,
    "geopf_start_row": 704,
    "geopf_max_search": 2,
    "geopf_coverage_search": 10,
    "geopf_detail_preset": "Sehr detailreich",
    "geopf_area_preset": "Nah",
    "geopf_lat": 48.8566,
    "geopf_lon": 2.3522,
    "geopf_lat_min": 42.0,
    "geopf_lon_min": -5.5,
    "geopf_lat_max": 51.5,
    "geopf_lon_max": 8.5,
    "swiss_preset": "wanderkarte",
    "swiss_custom_layers": "",
    "swiss_include_closures": False,
    "swiss_bbox_mode": "GPS-Mittelpunkt",
    "swiss_center_x": 2689663.9204230155,
    "swiss_center_y": 1140148.1944826096,
    "swiss_center_lat": 46.4067,
    "swiss_center_lon": 8.6047,
    "swiss_lat_min": 45.7,
    "swiss_lon_min": 5.8,
    "swiss_lat_max": 47.9,
    "swiss_lon_max": 10.7,
    "swiss_area_km": 10,
    "swiss_area_preset": "Standard",
    "swiss_quality_preset": "Standard",
    "swiss_span_x": 10000.0,
    "swiss_span_y": 10000.0,
    "swiss_bbox_text": "2600000,1200000,2610000,1210000",
    "swiss_output_width": 2048,
    "swiss_output_height": 2048,
    "swiss_image_format": "image/png",
    "swiss_transparent": True,
    "swiss_time": "",
    "swiss_styles": "",
    "swiss_identify_closures": False,
    "swiss_identify_tolerance": 12,
    "openaip_display_mode": "Nur OpenAIP",
    "openaip_layer": "openaip",
    "openaip_basemap": "World_Topo_Map",
    "openaip_overlay_alpha": 220,
    "openaip_white_threshold": 248,
    "openaip_render_vector_debug": False,
    "openaip_enabled_layers": [],
    "openaip_area_mode": "GPS-Mittelpunkt",
    "openaip_zoom": 9,
    "openaip_lat": 52.5200,
    "openaip_lon": 13.4050,
    "openaip_radius": 2,
    "openaip_tile_x": 275,
    "openaip_tile_y": 167,
    "openaip_lat_min": 52.3,
    "openaip_lon_min": 13.1,
    "openaip_lat_max": 52.7,
    "openaip_lon_max": 13.8,
    "openaip_detail_preset": "Standard",
    "openaip_area_preset": "Nah",
    "openaip_png_zoom": 9,
    "openaip_png_lat": 52.5200,
    "openaip_png_lon": 13.4050,
    "openaip_png_radius": 2,
    "openaip_png_tile_x": 275,
    "openaip_png_tile_y": 167,
    "openaip_png_lat_min": 52.3,
    "openaip_png_lon_min": 13.1,
    "openaip_png_lat_max": 52.7,
    "openaip_png_lon_max": 13.8,
    "openaip_composite_zoom": 9,
    "openaip_composite_lat": 52.5200,
    "openaip_composite_lon": 13.4050,
    "openaip_composite_radius": 2,
    "openaip_composite_tile_x": 275,
    "openaip_composite_tile_y": 167,
    "openaip_composite_lat_min": 52.3,
    "openaip_composite_lon_min": 13.1,
    "openaip_composite_lat_max": 52.7,
    "openaip_composite_lon_max": 13.8,
}


def nearest_preset_label(value: int | float, preset_map: dict[str, int | float]) -> str:
    ordered_items = list(preset_map.items())
    if not ordered_items:
        raise ValueError("preset_map must not be empty")
    return min(ordered_items, key=lambda item: abs(float(item[1]) - float(value)))[0]


def adaptive_tile_radius(
    *,
    base_radius: int,
    detail_level: int,
    reference_level: int,
    min_radius: int = 0,
    max_radius: int | None = None,
    growth_exponent: float = 1.0,
) -> int:
    if base_radius <= 0:
        return max(0, min_radius)

    # Preserve the visible geographic area as detail increases. A higher zoom
    # level needs proportionally more tiles around the center point.
    scale = 2 ** ((int(detail_level) - int(reference_level)) * float(growth_exponent))
    radius = max(min_radius, int(round(int(base_radius) * scale)))
    if max_radius is not None:
        radius = min(radius, int(max_radius))
    return radius

SOURCE_HINTS = {
    SOURCE_OFM: (
        "Mittelpunkt oder geographischen Rahmen waehlen. "
        f"OFM hat regionale Abdeckung mit Luecken. Zoombereich: {OFM_MIN_ZOOM} bis {OFM_MAX_ZOOM}."
    ),
    SOURCE_GEOPF: (
        "Mittelpunkt oder geographischen Rahmen waehlen. "
        f"GeoPF wird auf die gueltige Frankreich-Abdeckung begrenzt. TileMatrix: {GEOPF_MIN_TILEMATRIX} bis {GEOPF_MAX_TILEMATRIX}."
    ),
    SOURCE_SWISS: (
        "Mittelpunkt oder geographischen Rahmen waehlen. GeoAdmin rendert das Bild direkt serverseitig. Diese WMS-Quelle hat keinen eigenen Zoom."
    ),
    SOURCE_OPENAIP: f"Darstellung, Detailstufe und Bereich waehlen. OpenAIP ist weltweit nutzbar. Geprueft bis Zoom {OPENAIP_MAX_ZOOM}.",
    SOURCE_OPENAIP_PNG: f"Detailstufe und Bereich waehlen. OpenAIP ist weltweit nutzbar. Geprueft bis Zoom {OPENAIP_MAX_ZOOM}.",
    SOURCE_OPENAIP_COMPOSITE: f"Detailstufe und Bereich waehlen. OpenAIP wird auf eine Grundkarte gelegt. Geprueft bis Zoom {OPENAIP_MAX_ZOOM}.",
}


def merged_ui_state_defaults() -> dict[str, object]:
    merged_state = dict(UI_STATE_DEFAULTS)
    merged_state.update(normalize_persisted_ui_state(load_persisted_ui_state()))
    return merged_state


def _coerce_float(value: object, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not math.isfinite(number):
        return float(default)
    return number


def _sanitize_persisted_center_pair(state: dict[str, object], lat_key: str, lon_key: str) -> None:
    default_lat = float(UI_STATE_DEFAULTS[lat_key])
    default_lon = float(UI_STATE_DEFAULTS[lon_key])
    lat = _coerce_float(state.get(lat_key, default_lat), default_lat)
    lon = _coerce_float(state.get(lon_key, default_lon), default_lon)

    if abs(lat) < 1e-9 and abs(lon) < 1e-9:
        state[lat_key] = default_lat
        state[lon_key] = default_lon
        return

    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        state[lat_key] = default_lat
        state[lon_key] = default_lon
        return

    state[lat_key] = lat
    state[lon_key] = lon


def _sanitize_persisted_bbox(state: dict[str, object], lat_min_key: str, lon_min_key: str, lat_max_key: str, lon_max_key: str) -> None:
    default_lat_min = float(UI_STATE_DEFAULTS[lat_min_key])
    default_lon_min = float(UI_STATE_DEFAULTS[lon_min_key])
    default_lat_max = float(UI_STATE_DEFAULTS[lat_max_key])
    default_lon_max = float(UI_STATE_DEFAULTS[lon_max_key])
    lat_min = _coerce_float(state.get(lat_min_key, default_lat_min), default_lat_min)
    lon_min = _coerce_float(state.get(lon_min_key, default_lon_min), default_lon_min)
    lat_max = _coerce_float(state.get(lat_max_key, default_lat_max), default_lat_max)
    lon_max = _coerce_float(state.get(lon_max_key, default_lon_max), default_lon_max)

    if abs(lat_min) < 1e-9 and abs(lon_min) < 1e-9 and abs(lat_max) < 1e-9 and abs(lon_max) < 1e-9:
        state[lat_min_key] = default_lat_min
        state[lon_min_key] = default_lon_min
        state[lat_max_key] = default_lat_max
        state[lon_max_key] = default_lon_max
        return

    is_valid = (
        -90.0 <= lat_min <= 90.0
        and -90.0 <= lat_max <= 90.0
        and -180.0 <= lon_min <= 180.0
        and -180.0 <= lon_max <= 180.0
        and lat_max > lat_min
        and lon_max > lon_min
    )
    if not is_valid:
        state[lat_min_key] = default_lat_min
        state[lon_min_key] = default_lon_min
        state[lat_max_key] = default_lat_max
        state[lon_max_key] = default_lon_max
        return

    state[lat_min_key] = lat_min
    state[lon_min_key] = lon_min
    state[lat_max_key] = lat_max
    state[lon_max_key] = lon_max


def normalize_persisted_ui_state(persisted: dict[str, object]) -> dict[str, object]:
    normalized = dict(persisted)

    for lat_key, lon_key in (
        ("ofm_lat", "ofm_lon"),
        ("geopf_lat", "geopf_lon"),
        ("swiss_center_lat", "swiss_center_lon"),
        ("openaip_lat", "openaip_lon"),
        ("openaip_png_lat", "openaip_png_lon"),
        ("openaip_composite_lat", "openaip_composite_lon"),
    ):
        _sanitize_persisted_center_pair(normalized, lat_key, lon_key)

    for lat_min_key, lon_min_key, lat_max_key, lon_max_key in (
        ("ofm_lat_min", "ofm_lon_min", "ofm_lat_max", "ofm_lon_max"),
        ("geopf_lat_min", "geopf_lon_min", "geopf_lat_max", "geopf_lon_max"),
        ("swiss_lat_min", "swiss_lon_min", "swiss_lat_max", "swiss_lon_max"),
        ("openaip_lat_min", "openaip_lon_min", "openaip_lat_max", "openaip_lon_max"),
        ("openaip_png_lat_min", "openaip_png_lon_min", "openaip_png_lat_max", "openaip_png_lon_max"),
        (
            "openaip_composite_lat_min",
            "openaip_composite_lon_min",
            "openaip_composite_lat_max",
            "openaip_composite_lon_max",
        ),
    ):
        _sanitize_persisted_bbox(normalized, lat_min_key, lon_min_key, lat_max_key, lon_max_key)

    return normalized


def restore_source_state(session_state, source: str) -> None:
    merged_state = merged_ui_state_defaults()
    key_prefix = f"{source}_"
    exact_keys = {f"{source}_output_filename"}

    for key, value in merged_state.items():
        if key.startswith(key_prefix) or key in exact_keys:
            session_state[key] = deepcopy(value)


def sanitize_source_state(session_state, source: str) -> None:
    if source == SOURCE_SWISS:
        _sanitize_persisted_center_pair(session_state, "swiss_center_lat", "swiss_center_lon")
        _sanitize_persisted_bbox(session_state, "swiss_lat_min", "swiss_lon_min", "swiss_lat_max", "swiss_lon_max")
        return

    if source == SOURCE_OFM:
        prefix = "ofm"
    elif source == SOURCE_GEOPF:
        prefix = "geopf"
    else:
        prefix = "openaip"

    _sanitize_persisted_center_pair(session_state, f"{prefix}_lat", f"{prefix}_lon")
    _sanitize_persisted_bbox(session_state, f"{prefix}_lat_min", f"{prefix}_lon_min", f"{prefix}_lat_max", f"{prefix}_lon_max")


def ensure_source_state(session_state, source: str) -> None:
    merged_state = merged_ui_state_defaults()
    key_prefix = f"{source}_"
    exact_keys = {f"{source}_output_filename"}

    for key, value in merged_state.items():
        if not (key.startswith(key_prefix) or key in exact_keys):
            continue
        if key not in session_state or session_state[key] is None:
            session_state[key] = deepcopy(value)
    sanitize_source_state(session_state, source)


def init_state() -> None:
    merged_state = merged_ui_state_defaults()
    for key, value in merged_state.items():
        if key not in st.session_state or st.session_state[key] is None:
            st.session_state[key] = deepcopy(value)


def current_bounds(center_x: int, center_y: int, radius: int) -> Bounds:
    return Bounds(
        min_x=int(center_x) - int(radius),
        max_x=int(center_x) + int(radius),
        min_y=int(center_y) - int(radius),
        max_y=int(center_y) + int(radius),
    )


def stitch_with_progress(fetch_tile, bounds: Bounds, background=(255, 255, 255)):
    progress = st.progress(0, text="Lade Tiles: 0%")
    first_tile = None
    first_coords: tuple[int, int] | None = None

    for y in range(bounds.min_y, bounds.max_y + 1):
        for x in range(bounds.min_x, bounds.max_x + 1):
            first_tile = fetch_tile(x, y)
            if first_tile is not None:
                first_coords = (x, y)
                break
        if first_tile is not None:
            break

    if first_tile is None:
        progress.empty()
        raise ValueError("Im angeforderten Bereich wurden keine Tiles gefunden.")

    tile_width, tile_height = first_tile.size
    total_tiles = bounds.width * bounds.height
    has_alpha = first_tile.mode in {"RGBA", "LA"}
    canvas_mode = "RGBA" if has_alpha else "RGB"
    canvas_background = (*background, 0) if has_alpha else background
    image = Image.new(canvas_mode, (bounds.width * tile_width, bounds.height * tile_height), canvas_background)
    loaded_tiles = 0
    processed_tiles = 0

    for y in range(bounds.min_y, bounds.max_y + 1):
        for x in range(bounds.min_x, bounds.max_x + 1):
            use_first = first_tile is not None and first_coords == (x, y)
            tile = first_tile if use_first else fetch_tile(x, y)
            if tile is not None:
                px = (x - bounds.min_x) * tile_width
                py = (y - bounds.min_y) * tile_height
                if tile.mode in {"RGBA", "LA"}:
                    tile_rgba = tile.convert("RGBA")
                    image.paste(tile_rgba, (px, py), tile_rgba)
                else:
                    image.paste(tile, (px, py))
                loaded_tiles += 1
                if use_first:
                    first_tile = None

            processed_tiles += 1
            percent = int(processed_tiles / total_tiles * 100)
            progress.progress(percent, text=f"Lade Tiles: {percent}%")

    progress.progress(100, text="Lade Tiles: 100%")
    return bounds, image, loaded_tiles, total_tiles


def discover_source_bounds(fetch_tile, start_x: int, start_y: int, max_search: int) -> Bounds | None:
    try:
        if fetch_tile(start_x, start_y) is None:
            return None
        return find_bounds(fetch_tile=fetch_tile, start_x=start_x, start_y=start_y, max_search=max_search)
    except Exception:
        return None


def scaled_preview(image: Image.Image, max_width: int = 1400) -> Image.Image:
    if image.width <= max_width:
        return image
    scale = max_width / image.width
    preview_height = max(1, int(image.height * scale))
    return image.resize((max_width, preview_height), Image.Resampling.LANCZOS)


def apply_overlay(base_image: Image.Image, overlay_image: Image.Image, overlay_alpha: int, white_threshold: int) -> Image.Image:
    base_rgba = base_image.convert("RGBA")
    overlay_rgba = overlay_image.convert("RGBA")
    processed: list[tuple[int, int, int, int]] = []

    for r, g, b, a in overlay_rgba.getdata():
        if r >= white_threshold and g >= white_threshold and b >= white_threshold:
            processed.append((r, g, b, 0))
        else:
            processed.append((r, g, b, min(a, overlay_alpha)))

    overlay_rgba.putdata(processed)
    base_rgba.alpha_composite(overlay_rgba)
    return base_rgba.convert("RGB")


def alpha_composite_images(base_image: Image.Image, overlay_image: Image.Image) -> Image.Image:
    base_rgba = base_image.convert("RGBA")
    overlay_rgba = overlay_image.convert("RGBA")
    base_rgba.alpha_composite(overlay_rgba)
    return base_rgba.convert("RGB")


def choose_output_directory() -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return None

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(
            initialdir=st.session_state.output_directory,
            title="Ausgabeordner waehlen",
        )
    finally:
        root.destroy()
    return selected or None


def resolve_output_path(directory: str, filename: str) -> Path:
    clean_name = Path(filename).name or "karte.png"
    target_dir = Path(directory).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / clean_name


def feature_rows(features: list[dict]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for feature in features:
        attributes = feature.get("properties") or feature.get("attributes") or {}
        rows.append(
            {
                "Layer": str(feature.get("layerBodId") or feature.get("layerName") or SWISS_CLOSURES_LAYER),
                "Titel": str(attributes.get("title") or attributes.get("bezeichnung") or attributes.get("name") or ""),
                "Status": str(attributes.get("status") or attributes.get("zustand") or ""),
                "Beschreibung": str(
                    attributes.get("description")
                    or attributes.get("umleitung")
                    or attributes.get("reason")
                    or attributes.get("bemerkung")
                    or ""
                ),
                "Von": str(attributes.get("startdate") or attributes.get("from") or ""),
                "Bis": str(attributes.get("enddate") or attributes.get("to") or ""),
            }
        )
    return rows


def sync_zoom_scaled_state(
    *,
    state_prefix: str,
    current_zoom: int,
    x_key: str,
    y_key: str,
    radius_keys: list[str],
    bounds_by_zoom: dict[int, tuple[int, int, int, int]] | None = None,
) -> None:
    last_zoom_key = f"{state_prefix}_last_zoom"
    previous_zoom = int(st.session_state.get(last_zoom_key, current_zoom))
    current_zoom = int(current_zoom)
    if previous_zoom == current_zoom:
        return

    if bounds_by_zoom and previous_zoom in bounds_by_zoom and current_zoom in bounds_by_zoom:
        old_min_x, old_max_x, old_min_y, old_max_y = bounds_by_zoom[previous_zoom]
        new_min_x, new_max_x, new_min_y, new_max_y = bounds_by_zoom[current_zoom]
        st.session_state[x_key] = _remap_value_between_ranges(st.session_state[x_key], old_min_x, old_max_x, new_min_x, new_max_x)
        st.session_state[y_key] = _remap_value_between_ranges(st.session_state[y_key], old_min_y, old_max_y, new_min_y, new_max_y)
    else:
        st.session_state[x_key] = _scale_integer_for_zoom(st.session_state[x_key], previous_zoom, current_zoom)
        st.session_state[y_key] = _scale_integer_for_zoom(st.session_state[y_key], previous_zoom, current_zoom)

    for radius_key in radius_keys:
        st.session_state[radius_key] = max(
            1 if radius_key.endswith("coverage_search") else 0,
            _scale_integer_for_zoom(st.session_state[radius_key], previous_zoom, current_zoom),
        )
    st.session_state[last_zoom_key] = current_zoom


def _scale_integer_for_zoom(value: int, old_zoom: int, new_zoom: int) -> int:
    if old_zoom == new_zoom:
        return int(value)
    delta = int(new_zoom) - int(old_zoom)
    if delta > 0:
        return int(value) * (2 ** delta)
    return max(0, int(value) // (2 ** abs(delta)))


def _remap_value_between_ranges(value: int, old_min: int, old_max: int, new_min: int, new_max: int) -> int:
    if old_max <= old_min:
        return max(new_min, min(new_max, int(value)))
    ratio = (int(value) - old_min) / (old_max - old_min)
    mapped = round(new_min + ratio * (new_max - new_min))
    return max(new_min, min(new_max, mapped))


def suggested_output_name(config: UIConfig) -> str:
    if isinstance(config, OfmUIConfig):
        if config.render_mode == "composite":
            return "ofm_base_aero.png"
        return "ofm_base.jpg" if config.chart_type == "base" else "ofm_aero.png"
    if isinstance(config, GeoPfUIConfig):
        return "geopf_france.jpg"
    if isinstance(config, SwissUIConfig):
        return "schweizer_wanderkarte.png" if config.image_format == "image/png" else "schweizer_wanderkarte.jpg"
    if config.source == SOURCE_OPENAIP_PNG:
        return f"openaip_{config.layer}.png"
    return f"openaip_composite_{config.layer}.png"


def section_header(title: str, text: str) -> None:
    st.subheader(title)
    st.caption(text)


def effective_bounds_label(bounds: Bounds) -> str:
    return f"X {bounds.min_x}..{bounds.max_x}, Y {bounds.min_y}..{bounds.max_y} ({bounds.width}x{bounds.height} Tiles)"


def warn_if_large_request(config: UIConfig) -> None:
    source = config.source
    if source in {SOURCE_OFM, SOURCE_GEOPF, SOURCE_OPENAIP_PNG, SOURCE_OPENAIP_COMPOSITE} and getattr(config, "bounds", None) is not None:
        bounds = getattr(config, "bounds")
        tile_count = bounds.width * bounds.height
        if tile_count >= 121:
            st.warning(f"Der Bereich umfasst {tile_count} Tiles. Vorschau und Download koennen spuerbar Speicher und Zeit benoetigen.")
    if isinstance(config, SwissUIConfig):
        pixel_count = int(config.output_width) * int(config.output_height)
        if pixel_count >= 16_000_000:
            st.warning(
                f"Die Zielgroesse liegt bei {int(config.output_width)}x{int(config.output_height)} Pixel. "
                "Das ist fuer eine WMS-Ausgabe bereits recht gross."
            )


def ensure_output_filename(source: str, suggested: str) -> str:
    key = f"{source}_output_filename"
    if key not in st.session_state or not st.session_state[key]:
        st.session_state[key] = suggested
    return st.text_input(
        "Dateiname",
        key=key,
        help="Nur der Dateiname. Der Ordner wird links festgelegt.",
    )


def render_output_sidebar() -> None:
    with st.sidebar:
        st.markdown("### Ausgabeordner")
        st.text_input(
            "Ordner",
            key="output_directory",
            help="Zielordner fuer Karten und Vorschaudateien.",
        )
        if st.button("Durchsuchen", help="Oeffnet einen nativen Dialog zur Ordnerauswahl."):
            selected_directory = choose_output_directory()
            if selected_directory is None:
                st.warning("Kein Ordner ausgewaehlt.")
            else:
                st.session_state.output_directory = selected_directory
        if st.button("UI-Einstellungen zuruecksetzen", help="Setzt die lokal gespeicherten Einstellungen auf die Standardwerte zurueck."):
            reset_ui_state()
        st.caption("Die letzten UI-Einstellungen werden lokal gespeichert.")
        st.caption("Die Vorschau bleibt klein. Die gespeicherte Datei bleibt voll aufgeloest.")


def reset_ui_state() -> None:
    clear_persisted_ui_state()
    for key in list(st.session_state.keys()):
        if should_persist_ui_key(str(key)):
            del st.session_state[key]
    st.rerun()
