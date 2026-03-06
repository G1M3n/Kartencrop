from __future__ import annotations

from pathlib import Path

import streamlit as st
from PIL import Image

from .cache import cached_tile_fetch
from .openaip import fetch_vector_tile, openaip_session
from .openaip_render import decode_vector_tile, render_vector_tile
from .providers import EsriProvider, GeoPfProvider, OpenAipRasterProvider, OpenFlightMapsProvider
from .swissgeo import SwissGeoAdminFeatureProvider, SwissGeoAdminWmsProvider, scaled_dimensions
from .tiles import (
    Bounds,
    find_connected_bounds,
    find_nearest_valid_tile,
    render_composite_tiles_to_output,
    render_tiles_to_output,
    save_with_preview,
)
from .ui_models import GeoPfUIConfig, OfmUIConfig, OpenAipUIConfig, SwissUIConfig, UIConfig
from .ui_shared import (
    SOURCE_GEOPF,
    SOURCE_OFM,
    SOURCE_OPENAIP_COMPOSITE,
    SOURCE_OPENAIP_PNG,
    SOURCE_SWISS,
    alpha_composite_images,
    apply_overlay,
    current_bounds,
    discover_source_bounds,
    effective_bounds_label,
    feature_rows,
    scaled_preview,
    stitch_with_progress,
)


def _display_swiss_features(features: list[dict] | None, title: str) -> None:
    if features is None:
        st.warning("Sperrungsdetails konnten nicht geladen werden.")
        return
    st.caption(f"{title}: {len(features)} Treffer")
    if features:
        st.dataframe(feature_rows(features), use_container_width=True)


def _progress_callback(label: str):
    progress = st.progress(0, text=f"{label}: 0%")
    last_percent = -1

    def callback(processed_tiles: int, total_tiles: int) -> None:
        nonlocal last_percent
        percent = 100 if total_tiles <= 0 else int(processed_tiles / total_tiles * 100)
        if percent != last_percent:
            progress.progress(percent, text=f"{label}: {percent}%")
            last_percent = percent

    return progress, callback


def _show_low_memory_hint(used_low_memory: bool) -> None:
    if used_low_memory:
        st.caption("Speicherschonender Renderpfad aktiv.")


def _prepare_openaip_overlay_tile(tile: Image.Image, overlay_alpha: int, white_threshold: int) -> Image.Image:
    overlay_rgba = tile.convert("RGBA")
    processed: list[tuple[int, int, int, int]] = []
    for r, g, b, a in overlay_rgba.getdata():
        if r >= white_threshold and g >= white_threshold and b >= white_threshold:
            processed.append((r, g, b, 0))
        else:
            processed.append((r, g, b, min(a, overlay_alpha)))
    overlay_rgba.putdata(processed)
    return overlay_rgba


def _ofm_target_bounds(config: OfmUIConfig, fetch_tile) -> tuple[Bounds, Bounds | None, tuple[int, int] | None]:
    if config.area_strategy == "bounds" and config.bounds is not None:
        return config.bounds, None, None

    corrected = find_nearest_valid_tile(fetch_tile, config.start_x, config.start_y, max_distance=6)
    if corrected is None:
        raise ValueError("Fuer diesen OFM-Startpunkt wurden keine Tiles gefunden.")
    start_x, start_y = corrected
    if config.use_detected_range:
        try:
            detected = find_connected_bounds(fetch_tile, start_x, start_y, config.coverage_search)
        except ValueError as exc:
            raise ValueError("Fuer diesen OFM-Startpunkt wurden keine Tiles gefunden.") from exc
        return detected, detected, corrected
    return current_bounds(start_x, start_y, config.radius), None, corrected


def _geopf_target_bounds(config: GeoPfUIConfig, fetch_tile) -> tuple[Bounds, Bounds | None, tuple[int, int] | None]:
    if config.area_strategy == "bounds" and config.bounds is not None:
        return config.bounds, None, None

    corrected = find_nearest_valid_tile(fetch_tile, config.start_x, config.start_y, max_distance=2)
    if corrected is None:
        raise ValueError("Fuer diese GeoPF-Koordinaten wurden keine Tiles gefunden.")
    start_x, start_y = corrected
    if config.use_detected_range:
        detected = discover_source_bounds(fetch_tile, start_x, start_y, config.coverage_search)
        if detected is None:
            raise ValueError("Fuer diese GeoPF-Koordinaten wurden keine Tiles gefunden.")
        return detected, detected, corrected
    return current_bounds(start_x, start_y, config.radius), None, corrected


def run_preview(config: UIConfig) -> None:
    st.subheader("Vorschau")
    source = config.source
    if source == SOURCE_OFM:
        assert isinstance(config, OfmUIConfig)
        if config.render_mode == "composite":
            base_provider = OpenFlightMapsProvider(zoom=config.zoom, cycle=config.cycle, chart_type="base")
            base_fetch = cached_tile_fetch(base_provider.fetch_tile, namespace=base_provider.cache_namespace())
            bounds, detected, corrected = _ofm_target_bounds(config, base_fetch)
            _, base_image, loaded_tiles, total_tiles = stitch_with_progress(base_fetch, bounds)
            overlay_provider = OpenFlightMapsProvider(zoom=config.zoom, cycle=config.cycle, chart_type="aero", preserve_alpha=True)
            overlay_fetch = cached_tile_fetch(overlay_provider.fetch_tile, namespace=overlay_provider.cache_namespace())
            _, overlay_image, overlay_loaded, overlay_total = stitch_with_progress(overlay_fetch, bounds)
            image = alpha_composite_images(base_image, overlay_image)
            st.image(scaled_preview(image), caption="OpenFlightMaps Vorschau (base + aero)")
            st.caption(f"Basis-Tiles: {loaded_tiles}/{total_tiles} | Aero-Tiles: {overlay_loaded}/{overlay_total}")
        else:
            provider = OpenFlightMapsProvider(zoom=config.zoom, cycle=config.cycle, chart_type=config.chart_type, preserve_alpha=config.chart_type == "aero")
            cached_fetch = cached_tile_fetch(provider.fetch_tile, namespace=provider.cache_namespace())
            bounds, detected, corrected = _ofm_target_bounds(config, cached_fetch)
            _, image, loaded_tiles, total_tiles = stitch_with_progress(cached_fetch, bounds)
            st.image(scaled_preview(image), caption=f"OpenFlightMaps Vorschau ({config.chart_type})")
            st.caption(f"Geladene Tiles: {loaded_tiles}/{total_tiles}")
        st.caption(f"Bereich: {effective_bounds_label(bounds)}")
        if corrected is not None and corrected != (config.start_x, config.start_y):
            st.caption(f"Start-Tile korrigiert auf X {corrected[0]}, Y {corrected[1]}")
        if detected is not None:
            st.caption(f"Gefundene OFM-Grenzen: {effective_bounds_label(detected)}")
        return

    if source == SOURCE_GEOPF:
        assert isinstance(config, GeoPfUIConfig)
        provider = GeoPfProvider(tilematrix=config.tilematrix)
        cached_fetch = cached_tile_fetch(provider.fetch_tile, namespace=provider.cache_namespace())
        bounds, detected, corrected = _geopf_target_bounds(config, cached_fetch)
        _, image, loaded_tiles, total_tiles = stitch_with_progress(cached_fetch, bounds, background=(200, 200, 200))
        st.image(scaled_preview(image), caption="GeoPF Vorschau")
        st.caption(f"Geladene Tiles: {loaded_tiles}/{total_tiles}")
        st.caption(f"Bereich: Spalten {bounds.min_x}..{bounds.max_x}, Zeilen {bounds.min_y}..{bounds.max_y}")
        if corrected is not None and corrected != (config.start_x, config.start_y):
            st.caption(f"Startpunkt korrigiert auf Spalte {corrected[0]}, Zeile {corrected[1]}")
        if detected is not None:
            st.caption(f"Gefundene GeoPF-Grenzen: Spalten {detected.min_x}..{detected.max_x}, Zeilen {detected.min_y}..{detected.max_y}")
        return

    if source == SOURCE_SWISS:
        assert isinstance(config, SwissUIConfig)
        if not config.layers:
            raise ValueError("Es ist kein Schweizer Layer aktiv.")
        if config.bbox is None:
            raise ValueError("Die Bounding-Box ist nicht gueltig.")
        preview_width, preview_height = scaled_dimensions(config.output_width, config.output_height, max_width=1400)
        image = SwissGeoAdminWmsProvider().fetch_map(
            layers=config.layers,
            bbox=config.bbox,
            width=preview_width,
            height=preview_height,
            image_format=config.image_format,
            transparent=config.transparent,
            time=config.time,
            styles=config.styles,
        )
        if image is None:
            raise ValueError("GeoAdmin WMS hat fuer diese Anfrage kein Bild geliefert.")
        st.image(image, caption="Schweizer Karten-Vorschau")
        st.caption(f"Bounding-Box: {config.bbox.as_wms_bbox()} | Vorschaugroesse: {preview_width}x{preview_height} | Layer: {config.layers}")
        if config.identify_closures:
            features = SwissGeoAdminFeatureProvider().identify_features(
                bbox=config.bbox,
                geometry_x=config.bbox.center_x,
                geometry_y=config.bbox.center_y,
                image_width=preview_width,
                image_height=preview_height,
                tolerance=config.identify_tolerance,
            )
            _display_swiss_features(features, "Sperrungsdetails am Mittelpunkt")
        return

    assert isinstance(config, OpenAipUIConfig)
    if not config.api_key:
        raise ValueError("OpenAIP benoetigt einen API-Schluessel.")
    overlay_provider = OpenAipRasterProvider(zoom=config.zoom, layer=config.layer, api_key=config.api_key)
    overlay_fetch = cached_tile_fetch(overlay_provider.fetch_tile, namespace=overlay_provider.cache_namespace())
    _, overlay_image, loaded_tiles, total_tiles = stitch_with_progress(overlay_fetch, config.bounds)
    if source == SOURCE_OPENAIP_PNG:
        st.image(scaled_preview(overlay_image), caption=f"OpenAIP Vorschau ({config.layer})")
        st.caption(f"Geladene Tiles: {loaded_tiles}/{total_tiles}")
        st.caption(f"Bereich: {effective_bounds_label(config.bounds)}")
        return

    base_provider = EsriProvider(zoom=config.zoom, service=config.basemap)
    base_fetch = cached_tile_fetch(base_provider.fetch_tile, namespace=base_provider.cache_namespace())
    _, base_image, _, _ = stitch_with_progress(base_fetch, config.bounds)
    composite = apply_overlay(base_image=base_image, overlay_image=overlay_image, overlay_alpha=config.overlay_alpha, white_threshold=config.white_threshold)
    st.image(scaled_preview(composite), caption=f"OpenAIP Vorschau ({config.layer} auf {config.basemap})")
    st.caption(f"Overlay-Tiles: {loaded_tiles}/{total_tiles} | Bereich: {effective_bounds_label(config.bounds)}")


def run_build(config: UIConfig, output_path: Path) -> None:
    st.subheader("Ergebnis")
    source = config.source
    if source == SOURCE_OFM:
        assert isinstance(config, OfmUIConfig)
        if config.render_mode == "composite":
            base_provider = OpenFlightMapsProvider(zoom=config.zoom, cycle=config.cycle, chart_type="base")
            base_fetch = cached_tile_fetch(base_provider.fetch_tile, namespace=base_provider.cache_namespace())
            bounds, detected, corrected = _ofm_target_bounds(config, base_fetch)
            overlay_provider = OpenFlightMapsProvider(zoom=config.zoom, cycle=config.cycle, chart_type="aero", preserve_alpha=True)
            overlay_fetch = cached_tile_fetch(overlay_provider.fetch_tile, namespace=overlay_provider.cache_namespace())
            progress, callback = _progress_callback("Baue Karte")
            result = render_composite_tiles_to_output(
                base_fetch_tile=base_fetch,
                overlay_fetch_tile=overlay_fetch,
                bounds=bounds,
                output_path=output_path,
                show_progress=False,
                progress_callback=callback,
                preview_width=1400,
            )
            st.success(f"Gespeichert: {output_path}")
            st.image(str(result.preview_path), caption="OpenFlightMaps Ergebnis (base + aero)")
            st.caption(
                f"Basis-Tiles: {result.base_loaded_tiles}/{result.total_tiles} | "
                f"Aero-Tiles: {result.overlay_loaded_tiles}/{result.total_tiles}"
            )
            _show_low_memory_hint(result.used_low_memory)
        else:
            provider = OpenFlightMapsProvider(zoom=config.zoom, cycle=config.cycle, chart_type=config.chart_type, preserve_alpha=config.chart_type == "aero")
            cached_fetch = cached_tile_fetch(provider.fetch_tile, namespace=provider.cache_namespace())
            bounds, detected, corrected = _ofm_target_bounds(config, cached_fetch)
            progress, callback = _progress_callback("Baue Karte")
            result = render_tiles_to_output(
                fetch_tile=cached_fetch,
                bounds=bounds,
                output_path=output_path,
                show_progress=False,
                progress_callback=callback,
                preview_width=1400,
            )
            st.success(f"Gespeichert: {output_path}")
            st.image(str(result.preview_path), caption=f"OpenFlightMaps Ergebnis ({config.chart_type})")
            st.caption(f"Geladene Tiles: {result.loaded_tiles}/{result.total_tiles}")
            _show_low_memory_hint(result.used_low_memory)
        st.caption(f"Bereich: {effective_bounds_label(bounds)}")
        if corrected is not None and corrected != (config.start_x, config.start_y):
            st.caption(f"Start-Tile korrigiert auf X {corrected[0]}, Y {corrected[1]}")
        if detected is not None:
            st.caption(f"Gefundene OFM-Grenzen: {effective_bounds_label(detected)}")
        return

    if source == SOURCE_GEOPF:
        assert isinstance(config, GeoPfUIConfig)
        provider = GeoPfProvider(tilematrix=config.tilematrix)
        cached_fetch = cached_tile_fetch(provider.fetch_tile, namespace=provider.cache_namespace())
        bounds, detected, corrected = _geopf_target_bounds(config, cached_fetch)
        progress, callback = _progress_callback("Baue Karte")
        result = render_tiles_to_output(
            fetch_tile=cached_fetch,
            bounds=bounds,
            output_path=output_path,
            background=(200, 200, 200),
            show_progress=False,
            progress_callback=callback,
            preview_width=1400,
        )
        st.success(f"Gespeichert: {output_path}")
        st.image(str(result.preview_path), caption="GeoPF Ergebnis")
        st.caption(f"Geladene Tiles: {result.loaded_tiles}/{result.total_tiles}")
        _show_low_memory_hint(result.used_low_memory)
        st.caption(f"Bereich: Spalten {bounds.min_x}..{bounds.max_x}, Zeilen {bounds.min_y}..{bounds.max_y}")
        if corrected is not None and corrected != (config.start_x, config.start_y):
            st.caption(f"Startpunkt korrigiert auf Spalte {corrected[0]}, Zeile {corrected[1]}")
        if detected is not None:
            st.caption(f"Gefundene GeoPF-Grenzen: Spalten {detected.min_x}..{detected.max_x}, Zeilen {detected.min_y}..{detected.max_y}")
        return

    if source == SOURCE_SWISS:
        assert isinstance(config, SwissUIConfig)
        if not config.layers:
            raise ValueError("Es ist kein Schweizer Layer aktiv.")
        if config.bbox is None:
            raise ValueError("Die Bounding-Box ist nicht gueltig.")
        image = SwissGeoAdminWmsProvider().fetch_map(
            layers=config.layers,
            bbox=config.bbox,
            width=config.output_width,
            height=config.output_height,
            image_format=config.image_format,
            transparent=config.transparent,
            time=config.time,
            styles=config.styles,
        )
        if image is None:
            raise ValueError("GeoAdmin WMS hat fuer diese Anfrage kein Bild geliefert.")
        preview = save_with_preview(image, str(output_path), preview_width=1400)
        st.success(f"Gespeichert: {output_path}")
        st.image(preview, caption="Schweizer Karten-Ergebnis")
        st.caption(f"Bounding-Box: {config.bbox.as_wms_bbox()}")
        st.caption(f"Layer: {config.layers}")
        st.caption(f"Bildgroesse: {config.output_width}x{config.output_height} Pixel")
        if config.identify_closures:
            features = SwissGeoAdminFeatureProvider().identify_features(
                bbox=config.bbox,
                geometry_x=config.bbox.center_x,
                geometry_y=config.bbox.center_y,
                image_width=config.output_width,
                image_height=config.output_height,
                tolerance=config.identify_tolerance,
            )
            _display_swiss_features(features, "Sperrungsdetails am Mittelpunkt")
        return

    assert isinstance(config, OpenAipUIConfig)
    if not config.api_key:
        raise ValueError("OpenAIP benoetigt einen API-Schluessel.")
    overlay_provider = OpenAipRasterProvider(zoom=config.zoom, layer=config.layer, api_key=config.api_key)
    overlay_fetch = cached_tile_fetch(overlay_provider.fetch_tile, namespace=overlay_provider.cache_namespace())
    if source == SOURCE_OPENAIP_PNG:
        progress, callback = _progress_callback("Baue Karte")
        result = render_tiles_to_output(
            fetch_tile=overlay_fetch,
            bounds=config.bounds,
            output_path=output_path,
            show_progress=False,
            progress_callback=callback,
            preview_width=1400,
        )
        st.success(f"Gespeichert: {output_path}")
        st.image(str(result.preview_path), caption=f"OpenAIP Ergebnis ({config.layer})")
        st.caption(f"Bereich: {effective_bounds_label(config.bounds)}")
        st.caption(f"Geladene Tiles: {result.loaded_tiles}/{result.total_tiles}")
        _show_low_memory_hint(result.used_low_memory)
    else:
        base_provider = EsriProvider(zoom=config.zoom, service=config.basemap)
        base_fetch = cached_tile_fetch(base_provider.fetch_tile, namespace=base_provider.cache_namespace())
        progress, callback = _progress_callback("Baue Karte")
        result = render_composite_tiles_to_output(
            base_fetch_tile=base_fetch,
            overlay_fetch_tile=overlay_fetch,
            bounds=config.bounds,
            output_path=output_path,
            show_progress=False,
            progress_callback=callback,
            preview_width=1400,
            overlay_transform=lambda tile: _prepare_openaip_overlay_tile(
                tile,
                overlay_alpha=config.overlay_alpha,
                white_threshold=config.white_threshold,
            ),
        )
        st.success(f"Gespeichert: {output_path}")
        st.image(str(result.preview_path), caption=f"OpenAIP Composite ({config.layer} auf {config.basemap})")
        st.caption(f"Bereich: {effective_bounds_label(config.bounds)}")
        st.caption(
            f"Basis-Tiles: {result.base_loaded_tiles}/{result.total_tiles} | "
            f"Overlay-Tiles: {result.overlay_loaded_tiles}/{result.total_tiles}"
        )
        _show_low_memory_hint(result.used_low_memory)

    if config.render_vector_debug:
        session = openaip_session()
        tile_size = 512
        dbg = Image.new("RGB", (config.bounds.width * tile_size, config.bounds.height * tile_size), color=(245, 248, 252))
        for gy, ty in enumerate(range(config.bounds.min_y, config.bounds.max_y + 1)):
            for gx, tx in enumerate(range(config.bounds.min_x, config.bounds.max_x + 1)):
                result = fetch_vector_tile(z=config.zoom, x=tx, y=ty, api_key=config.api_key, session=session, layer="openaip")
                if not result.ok:
                    continue
                tile_data = decode_vector_tile(result.content)
                img = render_vector_tile(tile_data, tile_size=tile_size, enabled_layers=config.enabled_layers)
                dbg.paste(img, (gx * tile_size, gy * tile_size))
        dbg_out = output_path.with_name(f"{output_path.stem}_vector_debug.png")
        dbg.save(dbg_out)
        st.image(str(dbg_out), caption="OpenAIP Vektor-Diagnose")
        st.caption(f"Zusatzdatei: {dbg_out}")
