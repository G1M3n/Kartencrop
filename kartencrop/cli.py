from __future__ import annotations

import argparse
import json
from pathlib import Path


OFM_ANCHOR_SEARCH = 6
GEOPF_ANCHOR_SEARCH = 2


def _parse_regions(value: str) -> list[CropBox]:
    from .crop import CropBox

    boxes: list[CropBox] = []
    for chunk in value.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = [part.strip() for part in chunk.split(",")]
        if len(parts) != 4:
            raise argparse.ArgumentTypeError(
                "regions must be formatted as x1,y1,x2,y2;x1,y1,x2,y2"
            )
        x1, y1, x2, y2 = (int(p) for p in parts)
        boxes.append(CropBox(x1=x1, y1=y1, x2=x2, y2=y2))

    if not boxes:
        raise argparse.ArgumentTypeError("at least one crop region is required")
    return boxes


def _parse_swiss_bbox(value: str):
    from .swissgeo import parse_bbox

    try:
        return parse_bbox(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _resolve_anchor(fetch_tile, start_x: int, start_y: int, max_distance: int):
    from .tiles import find_nearest_valid_tile

    corrected = find_nearest_valid_tile(fetch_tile, start_x=start_x, start_y=start_y, max_distance=max_distance)
    if corrected is None:
        return None
    return corrected


def _ofm_bounds_from_bbox(zoom: int, lat_min: float, lon_min: float, lat_max: float, lon_max: float):
    from .geo import bbox_to_tile_bounds
    from .tiles import Bounds

    tile_bounds = bbox_to_tile_bounds(lat_min=lat_min, lon_min=lon_min, lat_max=lat_max, lon_max=lon_max, z=zoom)
    return Bounds(
        min_x=tile_bounds.min_x,
        max_x=tile_bounds.max_x,
        min_y=tile_bounds.min_y,
        max_y=tile_bounds.max_y,
    )


def _clip_geopf_bounds(tilematrix: int, bounds):
    from .providers import geopf_scan_oaci_limits
    from .tiles import clip_bounds

    min_col, max_col, min_row, max_row = geopf_scan_oaci_limits()[int(tilematrix)]
    return clip_bounds(bounds, min_x=min_col, max_x=max_col, min_y=min_row, max_y=max_row)


def _geopf_bounds_from_center(tilematrix: int, lat: float, lon: float, radius: int):
    from .geo import latlon_to_tile
    from .tiles import Bounds

    tile = latlon_to_tile(lat=lat, lon=lon, z=tilematrix)
    raw_bounds = Bounds(
        min_x=tile.x - int(radius),
        max_x=tile.x + int(radius),
        min_y=tile.y - int(radius),
        max_y=tile.y + int(radius),
    )
    return tile, _clip_geopf_bounds(tilematrix, raw_bounds)


def _geopf_bounds_from_bbox(tilematrix: int, lat_min: float, lon_min: float, lat_max: float, lon_max: float):
    from .geo import bbox_to_tile_bounds
    from .tiles import Bounds

    tile_bounds = bbox_to_tile_bounds(lat_min=lat_min, lon_min=lon_min, lat_max=lat_max, lon_max=lon_max, z=tilematrix)
    raw_bounds = Bounds(
        min_x=tile_bounds.min_x,
        max_x=tile_bounds.max_x,
        min_y=tile_bounds.min_y,
        max_y=tile_bounds.max_y,
    )
    return tile_bounds, _clip_geopf_bounds(tilematrix, raw_bounds)


def _print_ofm_hint() -> None:
    print("hint: OpenFlightMaps has irregular regional coverage with internal gaps.")
    print("hint: try a nearby start tile or use ofm-bbox / ofm-composite-bbox for explicit geographic areas.")


def _run_openflightmaps(args: argparse.Namespace) -> int:
    from .cache import cached_tile_fetch
    from .providers import OpenFlightMapsProvider
    from .tiles import find_connected_bounds, render_tiles_to_output

    try:
        provider = OpenFlightMapsProvider(
            zoom=args.zoom,
            cycle=args.cycle,
            chart_type=args.chart_type,
            timeout=args.timeout,
        )
    except ValueError as exc:
        print(str(exc))
        return 2
    cached_fetch = cached_tile_fetch(provider.fetch_tile, namespace=provider.cache_namespace())
    corrected = _resolve_anchor(cached_fetch, args.start_x, args.start_y, OFM_ANCHOR_SEARCH)
    if corrected is None:
        print("no chart data for this OpenFlightMaps start tile")
        _print_ofm_hint()
        return 2
    try:
        bounds = find_connected_bounds(
            fetch_tile=cached_fetch,
            start_x=corrected[0],
            start_y=corrected[1],
            max_search=args.max_search,
        )
        result = render_tiles_to_output(
            fetch_tile=cached_fetch,
            bounds=bounds,
            output_path=args.output,
            show_progress=not args.no_progress,
        )
    except ValueError as exc:
        print(str(exc))
        _print_ofm_hint()
        return 2

    print(f"output: {args.output}")
    print(f"preview: {result.preview_path}")
    if corrected != (args.start_x, args.start_y):
        print(f"adjusted start tile: x={corrected[0]} y={corrected[1]}")
    print(f"bounds: x={bounds.min_x}..{bounds.max_x}, y={bounds.min_y}..{bounds.max_y}")
    print(
        f"tiles: {result.loaded_tiles}/{result.total_tiles} "
        f"({result.loaded_tiles / result.total_tiles * 100:.1f}%)"
    )
    if result.used_low_memory:
        print("low-memory rendering: enabled")
    return 0


def _prepare_openaip_overlay_tile(tile, overlay_alpha: int, white_threshold: int):
    overlay_rgba = tile.convert("RGBA")
    processed: list[tuple[int, int, int, int]] = []
    for r, g, b, a in overlay_rgba.getdata():
        if r >= white_threshold and g >= white_threshold and b >= white_threshold:
            processed.append((r, g, b, 0))
        else:
            processed.append((r, g, b, min(a, overlay_alpha)))
    overlay_rgba.putdata(processed)
    return overlay_rgba


def _run_openflightmaps_composite(args: argparse.Namespace) -> int:
    from .cache import cached_tile_fetch
    from .providers import OpenFlightMapsProvider
    from .tiles import find_connected_bounds, render_composite_tiles_to_output

    try:
        base_provider = OpenFlightMapsProvider(
            zoom=args.zoom,
            cycle=args.cycle,
            chart_type="base",
            timeout=args.timeout,
        )
        overlay_provider = OpenFlightMapsProvider(
            zoom=args.zoom,
            cycle=args.cycle,
            chart_type="aero",
            preserve_alpha=True,
            timeout=args.timeout,
        )
    except ValueError as exc:
        print(str(exc))
        return 2
    base_fetch = cached_tile_fetch(base_provider.fetch_tile, namespace=base_provider.cache_namespace())
    corrected = _resolve_anchor(base_fetch, args.start_x, args.start_y, OFM_ANCHOR_SEARCH)
    if corrected is None:
        print("no chart data for this OpenFlightMaps start tile")
        _print_ofm_hint()
        return 2

    try:
        bounds = find_connected_bounds(
            fetch_tile=base_fetch,
            start_x=corrected[0],
            start_y=corrected[1],
            max_search=args.max_search,
        )
    except ValueError as exc:
        print(str(exc))
        print("hint: OpenFlightMaps base tiles were not found for this start tile.")
        return 2

    overlay_fetch = cached_tile_fetch(overlay_provider.fetch_tile, namespace=overlay_provider.cache_namespace())
    result = render_composite_tiles_to_output(
        base_fetch_tile=base_fetch,
        overlay_fetch_tile=overlay_fetch,
        bounds=bounds,
        output_path=args.output,
        show_progress=not args.no_progress,
    )

    print(f"output: {args.output}")
    print(f"preview: {result.preview_path}")
    if corrected != (args.start_x, args.start_y):
        print(f"adjusted start tile: x={corrected[0]} y={corrected[1]}")
    print(f"bounds: x={bounds.min_x}..{bounds.max_x}, y={bounds.min_y}..{bounds.max_y}")
    print(
        f"base tiles: {result.base_loaded_tiles}/{result.total_tiles} "
        f"({result.base_loaded_tiles / result.total_tiles * 100:.1f}%)"
    )
    print(
        f"aero tiles: {result.overlay_loaded_tiles}/{result.total_tiles} "
        f"({(result.overlay_loaded_tiles / result.total_tiles * 100) if result.total_tiles else 0:.1f}%)"
    )
    if result.used_low_memory:
        print("low-memory rendering: enabled")
    return 0


def _run_openflightmaps_bbox(args: argparse.Namespace) -> int:
    from .cache import cached_tile_fetch
    from .providers import OpenFlightMapsProvider
    from .tiles import render_tiles_to_output

    try:
        provider = OpenFlightMapsProvider(
            zoom=args.zoom,
            cycle=args.cycle,
            chart_type=args.chart_type,
            timeout=args.timeout,
        )
    except ValueError as exc:
        print(str(exc))
        return 2

    bounds = _ofm_bounds_from_bbox(
        zoom=args.zoom,
        lat_min=args.lat_min,
        lon_min=args.lon_min,
        lat_max=args.lat_max,
        lon_max=args.lon_max,
    )
    cached_fetch = cached_tile_fetch(provider.fetch_tile, namespace=provider.cache_namespace())

    try:
        result = render_tiles_to_output(
            fetch_tile=cached_fetch,
            bounds=bounds,
            output_path=args.output,
            show_progress=not args.no_progress,
        )
    except ValueError as exc:
        print(str(exc))
        print("hint: no OpenFlightMaps tiles were found anywhere inside this geographic frame.")
        _print_ofm_hint()
        return 2

    print(f"output: {args.output}")
    print(f"preview: {result.preview_path}")
    print(f"requested bbox: lat {args.lat_min}..{args.lat_max}, lon {args.lon_min}..{args.lon_max}")
    print(f"bounds: x={bounds.min_x}..{bounds.max_x}, y={bounds.min_y}..{bounds.max_y}")
    print(
        f"tiles: {result.loaded_tiles}/{result.total_tiles} "
        f"({result.loaded_tiles / result.total_tiles * 100:.1f}%)"
    )
    if result.used_low_memory:
        print("low-memory rendering: enabled")
    return 0


def _run_openflightmaps_composite_bbox(args: argparse.Namespace) -> int:
    from .cache import cached_tile_fetch
    from .providers import OpenFlightMapsProvider
    from .tiles import render_composite_tiles_to_output

    try:
        base_provider = OpenFlightMapsProvider(
            zoom=args.zoom,
            cycle=args.cycle,
            chart_type="base",
            timeout=args.timeout,
        )
        overlay_provider = OpenFlightMapsProvider(
            zoom=args.zoom,
            cycle=args.cycle,
            chart_type="aero",
            preserve_alpha=True,
            timeout=args.timeout,
        )
    except ValueError as exc:
        print(str(exc))
        return 2

    bounds = _ofm_bounds_from_bbox(
        zoom=args.zoom,
        lat_min=args.lat_min,
        lon_min=args.lon_min,
        lat_max=args.lat_max,
        lon_max=args.lon_max,
    )
    base_fetch = cached_tile_fetch(base_provider.fetch_tile, namespace=base_provider.cache_namespace())
    overlay_fetch = cached_tile_fetch(overlay_provider.fetch_tile, namespace=overlay_provider.cache_namespace())

    try:
        result = render_composite_tiles_to_output(
            base_fetch_tile=base_fetch,
            overlay_fetch_tile=overlay_fetch,
            bounds=bounds,
            output_path=args.output,
            show_progress=not args.no_progress,
        )
    except ValueError as exc:
        print(str(exc))
        print("hint: no OpenFlightMaps base tiles were found anywhere inside this geographic frame.")
        _print_ofm_hint()
        return 2
    print(f"output: {args.output}")
    print(f"preview: {result.preview_path}")
    print(f"requested bbox: lat {args.lat_min}..{args.lat_max}, lon {args.lon_min}..{args.lon_max}")
    print(f"bounds: x={bounds.min_x}..{bounds.max_x}, y={bounds.min_y}..{bounds.max_y}")
    print(
        f"base tiles: {result.base_loaded_tiles}/{result.total_tiles} "
        f"({result.base_loaded_tiles / result.total_tiles * 100:.1f}%)"
    )
    print(
        f"aero tiles: {result.overlay_loaded_tiles}/{result.total_tiles} "
        f"({(result.overlay_loaded_tiles / result.total_tiles * 100) if result.total_tiles else 0:.1f}%)"
    )
    if result.used_low_memory:
        print("low-memory rendering: enabled")
    return 0


def _run_openflightmaps_probe(args: argparse.Namespace) -> int:
    from .providers import OpenFlightMapsProvider

    provider = OpenFlightMapsProvider(
        zoom=args.zoom,
        cycle=args.cycle,
        chart_type=args.chart_type,
        timeout=args.timeout,
    )
    image = provider.fetch_tile(args.x, args.y)
    if image is None:
        print("no chart data for this tile")
        return 1

    print(f"tile ok: {image.width}x{image.height}")
    if args.output:
        image.save(args.output)
        print(f"saved: {args.output}")
    return 0


def _run_swiss_wms(args: argparse.Namespace) -> int:
    from .swissgeo import (
        SWISS_CLOSURES_LAYER,
        SWISS_WMS_LAYER_PRESETS,
        SwissGeoAdminFeatureProvider,
        SwissGeoAdminWmsProvider,
        bbox_from_center,
        bbox_from_wgs84_center,
        merge_layers,
    )
    from .tiles import save_with_preview

    provider = SwissGeoAdminWmsProvider(timeout=args.timeout)
    bbox = args.bbox
    if bbox is None:
        if args.center_lat is not None and args.center_lon is not None:
            bbox = bbox_from_wgs84_center(
                lat=args.center_lat,
                lon=args.center_lon,
                width_m=args.span_x,
                height_m=args.span_y,
            )
        else:
            bbox = bbox_from_center(
                center_x=args.center_x,
                center_y=args.center_y,
                width_m=args.span_x,
                height_m=args.span_y,
            )

    layers = args.layers or SWISS_WMS_LAYER_PRESETS[args.preset]
    if args.include_closures:
        layers = merge_layers(layers, SWISS_CLOSURES_LAYER)
    image = provider.fetch_map(
        layers=layers,
        bbox=bbox,
        width=args.width,
        height=args.height,
        crs=args.crs,
        image_format=args.image_format,
        transparent=not args.opaque,
        time=args.time,
        styles=args.styles,
    )
    if image is None:
        print("no image data returned from GeoAdmin WMS")
        print("hint: verify bbox, dimensions and layer names for the Swiss map request.")
        return 2

    preview_path = save_with_preview(image, args.output, preview_width=min(1400, args.width))
    print(f"output: {args.output}")
    print(f"preview: {preview_path}")
    print(f"layers: {layers}")
    print(f"bbox: {bbox.as_wms_bbox()} ({args.crs})")
    print(f"size: {args.width}x{args.height}")
    print(f"format: {args.image_format}")

    if args.identify_closures:
        feature_provider = SwissGeoAdminFeatureProvider(timeout=args.timeout)
        features = feature_provider.identify_features(
            bbox=bbox,
            geometry_x=bbox.center_x,
            geometry_y=bbox.center_y,
            image_width=args.width,
            image_height=args.height,
            tolerance=args.identify_tolerance,
        )
        if features is None:
            print("closures identify: request failed")
        else:
            print(f"closures identify count: {len(features)}")
            output_path = args.identify_output
            if output_path:
                Path(output_path).write_text(json.dumps(features, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"closures output: {output_path}")
    return 0


def _run_geopf(args: argparse.Namespace) -> int:
    from .cache import cached_tile_fetch
    from .providers import GeoPfProvider
    from .tiles import find_bounds, render_tiles_to_output

    try:
        provider = GeoPfProvider(tilematrix=str(args.tilematrix), timeout=args.timeout)
    except ValueError as exc:
        print(str(exc))
        return 2
    cached_fetch = cached_tile_fetch(provider.fetch_tile, namespace=provider.cache_namespace())
    corrected = _resolve_anchor(cached_fetch, args.start_col, args.start_row, GEOPF_ANCHOR_SEARCH)
    if corrected is None:
        print("no GeoPF tiles for this TileMatrix / col / row")
        print("hint: SCAN-OACI is currently verified for TileMatrix 6..11 and the documented col/row ranges of each TileMatrix.")
        return 2
    bounds = find_bounds(
        fetch_tile=cached_fetch,
        start_x=corrected[0],
        start_y=corrected[1],
        max_search=args.max_search,
    )
    result = render_tiles_to_output(
        fetch_tile=cached_fetch,
        bounds=bounds,
        output_path=args.output,
        show_progress=not args.no_progress,
        background=(200, 200, 200),
    )

    print(f"output: {args.output}")
    print(f"preview: {result.preview_path}")
    if corrected != (args.start_col, args.start_row):
        print(f"adjusted start point: col={corrected[0]} row={corrected[1]}")
    print(f"bounds: col={bounds.min_x}..{bounds.max_x}, row={bounds.min_y}..{bounds.max_y}")
    print(
        f"tiles: {result.loaded_tiles}/{result.total_tiles} "
        f"({result.loaded_tiles / result.total_tiles * 100:.1f}%)"
    )
    if result.used_low_memory:
        print("low-memory rendering: enabled")
    return 0


def _run_geopf_center(args: argparse.Namespace) -> int:
    from .cache import cached_tile_fetch
    from .providers import GeoPfProvider
    from .tiles import render_tiles_to_output

    try:
        provider = GeoPfProvider(tilematrix=str(args.tilematrix), timeout=args.timeout)
    except ValueError as exc:
        print(str(exc))
        return 2

    tile, bounds = _geopf_bounds_from_center(
        tilematrix=args.tilematrix,
        lat=args.lat,
        lon=args.lon,
        radius=args.radius,
    )
    if bounds is None:
        print("requested center lies outside the GeoPF France coverage for this TileMatrix")
        return 2

    cached_fetch = cached_tile_fetch(provider.fetch_tile, namespace=provider.cache_namespace())
    try:
        result = render_tiles_to_output(
            fetch_tile=cached_fetch,
            bounds=bounds,
            output_path=args.output,
            show_progress=not args.no_progress,
            background=(200, 200, 200),
        )
    except ValueError as exc:
        print(str(exc))
        print("hint: no GeoPF tiles were found in the requested area.")
        return 2

    print(f"output: {args.output}")
    print(f"preview: {result.preview_path}")
    print(f"center: lat={args.lat} lon={args.lon} -> col={tile.x} row={tile.y}")
    print(f"bounds: col={bounds.min_x}..{bounds.max_x}, row={bounds.min_y}..{bounds.max_y}")
    print(
        f"tiles: {result.loaded_tiles}/{result.total_tiles} "
        f"({result.loaded_tiles / result.total_tiles * 100:.1f}%)"
    )
    if result.used_low_memory:
        print("low-memory rendering: enabled")
    return 0


def _run_geopf_bbox(args: argparse.Namespace) -> int:
    from .cache import cached_tile_fetch
    from .providers import GeoPfProvider
    from .tiles import render_tiles_to_output

    try:
        provider = GeoPfProvider(tilematrix=str(args.tilematrix), timeout=args.timeout)
    except ValueError as exc:
        print(str(exc))
        return 2

    tile_bounds, bounds = _geopf_bounds_from_bbox(
        tilematrix=args.tilematrix,
        lat_min=args.lat_min,
        lon_min=args.lon_min,
        lat_max=args.lat_max,
        lon_max=args.lon_max,
    )
    if bounds is None:
        print("requested geographic frame lies outside the GeoPF France coverage for this TileMatrix")
        return 2

    cached_fetch = cached_tile_fetch(provider.fetch_tile, namespace=provider.cache_namespace())
    try:
        result = render_tiles_to_output(
            fetch_tile=cached_fetch,
            bounds=bounds,
            output_path=args.output,
            show_progress=not args.no_progress,
            background=(200, 200, 200),
        )
    except ValueError as exc:
        print(str(exc))
        print("hint: no GeoPF tiles were found in the requested area.")
        return 2

    print(f"output: {args.output}")
    print(f"preview: {result.preview_path}")
    print(f"requested bbox: lat {args.lat_min}..{args.lat_max}, lon {args.lon_min}..{args.lon_max}")
    print(f"raw tile bounds: col={tile_bounds.min_x}..{tile_bounds.max_x}, row={tile_bounds.min_y}..{tile_bounds.max_y}")
    print(f"clipped bounds: col={bounds.min_x}..{bounds.max_x}, row={bounds.min_y}..{bounds.max_y}")
    print(
        f"tiles: {result.loaded_tiles}/{result.total_tiles} "
        f"({result.loaded_tiles / result.total_tiles * 100:.1f}%)"
    )
    if result.used_low_memory:
        print("low-memory rendering: enabled")
    return 0


def _run_openaip_png_probe(args: argparse.Namespace) -> int:
    from .cache import cached_tile_fetch
    from .providers import OpenAipRasterProvider

    provider = OpenAipRasterProvider(
        zoom=args.zoom,
        layer=args.layer,
        api_key=args.api_key,
        timeout=args.timeout,
    )
    cached_fetch = cached_tile_fetch(provider.fetch_tile, namespace=provider.cache_namespace())
    image = cached_fetch(args.x, args.y)
    if image is None:
        print("no raster tile data for this coordinate")
        return 1

    print(f"tile ok: {image.width}x{image.height}")
    if args.output:
        image.save(args.output)
        print(f"saved: {args.output}")
    return 0


def _run_openaip_png_full(args: argparse.Namespace) -> int:
    from .cache import cached_tile_fetch
    from .providers import OpenAipRasterProvider
    from .tiles import find_bounds, render_tiles_to_output

    provider = OpenAipRasterProvider(
        zoom=args.zoom,
        layer=args.layer,
        api_key=args.api_key,
        timeout=args.timeout,
    )
    cached_fetch = cached_tile_fetch(provider.fetch_tile, namespace=provider.cache_namespace())
    try:
        bounds = find_bounds(
            fetch_tile=cached_fetch,
            start_x=args.start_x,
            start_y=args.start_y,
            max_search=args.max_search,
        )
    except ValueError as exc:
        print(str(exc))
        print("hint: verify coordinates with openaip-png-probe and check layer (openaip|hotspots).")
        return 2

    result = render_tiles_to_output(
        fetch_tile=cached_fetch,
        bounds=bounds,
        output_path=args.output,
        show_progress=not args.no_progress,
    )
    print(f"output: {args.output}")
    print(f"preview: {result.preview_path}")
    print(f"bounds: x={bounds.min_x}..{bounds.max_x}, y={bounds.min_y}..{bounds.max_y}")
    print(
        f"tiles: {result.loaded_tiles}/{result.total_tiles} "
        f"({result.loaded_tiles / result.total_tiles * 100:.1f}%)"
    )
    if result.used_low_memory:
        print("low-memory rendering: enabled")
    return 0


def _run_openaip_composite_full(args: argparse.Namespace) -> int:
    from .cache import cached_tile_fetch
    from .providers import EsriProvider, OpenAipRasterProvider
    from .tiles import find_bounds, render_composite_tiles_to_output

    overlay_provider = OpenAipRasterProvider(
        zoom=args.zoom,
        layer=args.layer,
        api_key=args.api_key,
        timeout=args.timeout,
    )
    overlay_fetch = cached_tile_fetch(overlay_provider.fetch_tile, namespace=overlay_provider.cache_namespace())
    try:
        bounds = find_bounds(
            fetch_tile=overlay_fetch,
            start_x=args.start_x,
            start_y=args.start_y,
            max_search=args.max_search,
        )
    except ValueError as exc:
        print(str(exc))
        print("hint: verify coordinates with openaip-png-probe and check layer (openaip|hotspots).")
        return 2

    base_provider = EsriProvider(zoom=args.zoom, service=args.basemap, timeout=args.timeout)
    base_fetch = cached_tile_fetch(base_provider.fetch_tile, namespace=base_provider.cache_namespace())
    result = render_composite_tiles_to_output(
        base_fetch_tile=base_fetch,
        overlay_fetch_tile=overlay_fetch,
        bounds=bounds,
        output_path=args.output,
        show_progress=not args.no_progress,
        overlay_transform=lambda tile: _prepare_openaip_overlay_tile(
            tile,
            overlay_alpha=args.overlay_alpha,
            white_threshold=args.white_threshold,
        ),
    )

    print(f"output: {args.output}")
    print(f"preview: {result.preview_path}")
    print(
        f"bounds: x={bounds.min_x}..{bounds.max_x}, "
        f"y={bounds.min_y}..{bounds.max_y}"
    )
    print(
        f"base tiles: {result.base_loaded_tiles}/{result.total_tiles} "
        f"({result.base_loaded_tiles / result.total_tiles * 100:.1f}%)"
    )
    print(
        f"overlay tiles: {result.overlay_loaded_tiles}/{result.total_tiles} "
        f"({result.overlay_loaded_tiles / result.total_tiles * 100:.1f}%)"
    )
    if result.used_low_memory:
        print("low-memory rendering: enabled")
    return 0


def _run_openaip_style(args: argparse.Namespace) -> int:
    from .openaip import fetch_style

    result = fetch_style(style=args.style, timeout=args.timeout)
    print(f"status: {result.status_code}")
    print(f"content-type: {result.content_type}")
    if not result.ok:
        print(result.content.decode("utf-8", errors="replace")[:400])
        return 1

    data = json.loads(result.content.decode("utf-8"))
    if args.output:
        Path(args.output).write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"saved: {args.output}")
    else:
        print(json.dumps(data, indent=2)[:1200])
    return 0


def _run_latlon_to_tile(args: argparse.Namespace) -> int:
    from .geo import latlon_to_tile

    tile = latlon_to_tile(lat=args.lat, lon=args.lon, z=args.zoom)
    print(f"x={tile.x} y={tile.y} z={tile.z}")
    return 0


def _run_bbox_to_tiles(args: argparse.Namespace) -> int:
    from .geo import bbox_to_tile_bounds

    bounds = bbox_to_tile_bounds(
        lat_min=args.lat_min,
        lon_min=args.lon_min,
        lat_max=args.lat_max,
        lon_max=args.lon_max,
        z=args.zoom,
    )
    max_search = max(bounds.width, bounds.height) // 2
    print(f"bounds: x={bounds.min_x}..{bounds.max_x}, y={bounds.min_y}..{bounds.max_y}, z={bounds.z}")
    print(f"suggested center: start-x={bounds.center_x} start-y={bounds.center_y}")
    print(f"suggested max-search: {max_search}")
    return 0


def _run_openaip_vector_grid(args: argparse.Namespace) -> int:
    from .openaip import fetch_vector_tile, openaip_session
    from .openaip_render import decode_vector_tile, render_vector_tile

    layers = [x.strip() for x in args.layers.split(",")] if args.layers else None
    session = openaip_session()
    tile_size = args.tile_size
    width = args.width
    height = args.height
    canvas = Path(args.output)
    from PIL import Image

    image = Image.new("RGB", (width * tile_size, height * tile_size), color=(245, 248, 252))
    loaded = 0
    for gy in range(height):
        for gx in range(width):
            x = args.start_x + gx
            y = args.start_y + gy
            result = fetch_vector_tile(
                z=args.zoom,
                x=x,
                y=y,
                session=session,
                api_key=args.api_key,
                layer="openaip",
            )
            if not result.ok:
                continue
            tile_data = decode_vector_tile(result.content)
            tile_img = render_vector_tile(tile_data, tile_size=tile_size, enabled_layers=layers)
            image.paste(tile_img, (gx * tile_size, gy * tile_size))
            loaded += 1

    image.save(canvas)
    print(f"saved: {canvas} ({image.width}x{image.height})")
    print(f"tiles: {loaded}/{width*height}")
    return 0


def _run_crop_percent(args: argparse.Namespace) -> int:
    from PIL import Image

    from .crop import crop_by_percentage

    image = Image.open(args.image)
    cropped, box = crop_by_percentage(
        image=image,
        center_x_pct=args.center_x_pct,
        center_y_pct=args.center_y_pct,
        width_pct=args.width_pct,
        height_pct=args.height_pct,
    )

    output = Path(args.output) if args.output else Path(args.image).with_name(f"{Path(args.image).stem}_crop.jpg")
    cropped.save(output, format="JPEG", quality=95)

    print(f"output: {output}")
    print(f"box: ({box.x1}, {box.y1}) -> ({box.x2}, {box.y2})")
    print(f"size: {box.width}x{box.height}")
    return 0


def _run_crop_regions(args: argparse.Namespace) -> int:
    from PIL import Image

    from .crop import crop_regions, save_cropped_regions

    image = Image.open(args.image)
    crops = crop_regions(image=image, boxes=args.regions)
    paths = save_cropped_regions(crops=crops, output_prefix=args.output_prefix)

    print(f"created {len(paths)} crops")
    for path in paths:
        print(path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    from .capabilities import get_geopf_tilematrix_range
    from .providers import (
        OFM_MAX_ZOOM,
        OFM_MIN_ZOOM,
        OPENAIP_MAX_ZOOM,
        OPENAIP_MIN_ZOOM,
    )
    geopf_min_tilematrix, geopf_max_tilematrix = get_geopf_tilematrix_range()

    parser = argparse.ArgumentParser(description="Kartencrop modular CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    ofm = sub.add_parser("ofm-full", help="Create connected OpenFlightMaps image from a start tile")
    ofm.add_argument("--zoom", type=int, required=True, choices=range(OFM_MIN_ZOOM, OFM_MAX_ZOOM + 1))
    ofm.add_argument("--start-x", type=int, required=True)
    ofm.add_argument("--start-y", type=int, required=True)
    ofm.add_argument("--cycle", default="latest")
    ofm.add_argument("--chart-type", choices=["aero", "base"], default="aero")
    ofm.add_argument("--max-search", type=int, default=50)
    ofm.add_argument("--timeout", type=float, default=10.0)
    ofm.add_argument("--output", default="openflightmaps_full.jpg")
    ofm.add_argument("--no-progress", action="store_true")
    ofm.set_defaults(func=_run_openflightmaps)

    ofm_bbox = sub.add_parser("ofm-bbox", help="Create OpenFlightMaps image for a geographic bounding box")
    ofm_bbox.add_argument("--zoom", type=int, required=True, choices=range(OFM_MIN_ZOOM, OFM_MAX_ZOOM + 1))
    ofm_bbox.add_argument("--lat-min", type=float, required=True)
    ofm_bbox.add_argument("--lon-min", type=float, required=True)
    ofm_bbox.add_argument("--lat-max", type=float, required=True)
    ofm_bbox.add_argument("--lon-max", type=float, required=True)
    ofm_bbox.add_argument("--cycle", default="latest")
    ofm_bbox.add_argument("--chart-type", choices=["aero", "base"], default="aero")
    ofm_bbox.add_argument("--timeout", type=float, default=10.0)
    ofm_bbox.add_argument("--output", default="openflightmaps_bbox.png")
    ofm_bbox.add_argument("--no-progress", action="store_true")
    ofm_bbox.set_defaults(func=_run_openflightmaps_bbox)

    ofm_composite = sub.add_parser("ofm-composite-full", help="Create connected OpenFlightMaps base+aero composite image")
    ofm_composite.add_argument("--zoom", type=int, required=True, choices=range(OFM_MIN_ZOOM, OFM_MAX_ZOOM + 1))
    ofm_composite.add_argument("--start-x", type=int, required=True)
    ofm_composite.add_argument("--start-y", type=int, required=True)
    ofm_composite.add_argument("--cycle", default="latest")
    ofm_composite.add_argument("--max-search", type=int, default=50)
    ofm_composite.add_argument("--timeout", type=float, default=10.0)
    ofm_composite.add_argument("--output", default="openflightmaps_composite.png")
    ofm_composite.add_argument("--no-progress", action="store_true")
    ofm_composite.set_defaults(func=_run_openflightmaps_composite)

    ofm_composite_bbox = sub.add_parser("ofm-composite-bbox", help="Create OpenFlightMaps base+aero composite for a geographic bounding box")
    ofm_composite_bbox.add_argument("--zoom", type=int, required=True, choices=range(OFM_MIN_ZOOM, OFM_MAX_ZOOM + 1))
    ofm_composite_bbox.add_argument("--lat-min", type=float, required=True)
    ofm_composite_bbox.add_argument("--lon-min", type=float, required=True)
    ofm_composite_bbox.add_argument("--lat-max", type=float, required=True)
    ofm_composite_bbox.add_argument("--lon-max", type=float, required=True)
    ofm_composite_bbox.add_argument("--cycle", default="latest")
    ofm_composite_bbox.add_argument("--timeout", type=float, default=10.0)
    ofm_composite_bbox.add_argument("--output", default="openflightmaps_composite_bbox.png")
    ofm_composite_bbox.add_argument("--no-progress", action="store_true")
    ofm_composite_bbox.set_defaults(func=_run_openflightmaps_composite_bbox)

    ofm_probe = sub.add_parser("ofm-probe", help="Probe a single OpenFlightMaps tile")
    ofm_probe.add_argument("--zoom", type=int, required=True, choices=range(OFM_MIN_ZOOM, OFM_MAX_ZOOM + 1))
    ofm_probe.add_argument("--x", type=int, required=True)
    ofm_probe.add_argument("--y", type=int, required=True)
    ofm_probe.add_argument("--cycle", default="latest")
    ofm_probe.add_argument("--chart-type", choices=["aero", "base"], default="aero")
    ofm_probe.add_argument("--timeout", type=float, default=10.0)
    ofm_probe.add_argument("--output")
    ofm_probe.set_defaults(func=_run_openflightmaps_probe)

    geopf = sub.add_parser("geopf-full", help="Create full GeoPF OACI image")
    geopf.add_argument("--tilematrix", type=int, default=11, choices=range(geopf_min_tilematrix, geopf_max_tilematrix + 1))
    geopf.add_argument("--start-col", type=int, required=True)
    geopf.add_argument("--start-row", type=int, required=True)
    geopf.add_argument("--max-search", type=int, default=50)
    geopf.add_argument("--timeout", type=float, default=10.0)
    geopf.add_argument("--output", default="geopf_full.jpg")
    geopf.add_argument("--no-progress", action="store_true")
    geopf.set_defaults(func=_run_geopf)

    geopf_center = sub.add_parser("geopf-center", help="Create GeoPF OACI image from a geographic center point")
    geopf_center.add_argument("--tilematrix", type=int, default=11, choices=range(geopf_min_tilematrix, geopf_max_tilematrix + 1))
    geopf_center.add_argument("--lat", type=float, required=True)
    geopf_center.add_argument("--lon", type=float, required=True)
    geopf_center.add_argument("--radius", type=int, default=2)
    geopf_center.add_argument("--timeout", type=float, default=10.0)
    geopf_center.add_argument("--output", default="geopf_center.jpg")
    geopf_center.add_argument("--no-progress", action="store_true")
    geopf_center.set_defaults(func=_run_geopf_center)

    geopf_bbox = sub.add_parser("geopf-bbox", help="Create GeoPF OACI image for a geographic bounding box")
    geopf_bbox.add_argument("--tilematrix", type=int, default=11, choices=range(geopf_min_tilematrix, geopf_max_tilematrix + 1))
    geopf_bbox.add_argument("--lat-min", type=float, required=True)
    geopf_bbox.add_argument("--lon-min", type=float, required=True)
    geopf_bbox.add_argument("--lat-max", type=float, required=True)
    geopf_bbox.add_argument("--lon-max", type=float, required=True)
    geopf_bbox.add_argument("--timeout", type=float, default=10.0)
    geopf_bbox.add_argument("--output", default="geopf_bbox.jpg")
    geopf_bbox.add_argument("--no-progress", action="store_true")
    geopf_bbox.set_defaults(func=_run_geopf_bbox)

    swiss = sub.add_parser("swiss-wms", help="Render Swiss GeoAdmin WMS map by LV95 bounding box")
    swiss.add_argument("--preset", choices=["wanderkarte", "pixelkarte-farbe", "wanderwege", "zeitreihe"], default="wanderkarte")
    swiss.add_argument("--layers")
    swiss.add_argument("--bbox", type=_parse_swiss_bbox)
    swiss.add_argument("--center-x", type=float, default=2626772.3)
    swiss.add_argument("--center-y", type=float, default=1178584.47)
    swiss.add_argument("--center-lat", type=float)
    swiss.add_argument("--center-lon", type=float)
    swiss.add_argument("--span-x", type=float, default=10000.0)
    swiss.add_argument("--span-y", type=float, default=10000.0)
    swiss.add_argument("--width", type=int, default=2048)
    swiss.add_argument("--height", type=int, default=2048)
    swiss.add_argument("--crs", default="EPSG:2056")
    swiss.add_argument("--image-format", choices=["image/png", "image/jpeg"], default="image/png")
    swiss.add_argument("--opaque", action="store_true")
    swiss.add_argument("--include-closures", action="store_true")
    swiss.add_argument("--identify-closures", action="store_true")
    swiss.add_argument("--identify-tolerance", type=int, default=12)
    swiss.add_argument("--identify-output")
    swiss.add_argument("--time")
    swiss.add_argument("--styles", default="")
    swiss.add_argument("--timeout", type=float, default=20.0)
    swiss.add_argument("--output", default="swiss_wanderkarte.png")
    swiss.set_defaults(func=_run_swiss_wms)

    openaip_probe = sub.add_parser("openaip-png-probe", help="Probe a single OpenAIP PNG tile")
    openaip_probe.add_argument("--zoom", type=int, required=True, choices=range(OPENAIP_MIN_ZOOM, OPENAIP_MAX_ZOOM + 1))
    openaip_probe.add_argument("--x", type=int, required=True)
    openaip_probe.add_argument("--y", type=int, required=True)
    openaip_probe.add_argument("--layer", choices=["openaip", "hotspots"], default="openaip")
    openaip_probe.add_argument("--api-key")
    openaip_probe.add_argument("--timeout", type=float, default=15.0)
    openaip_probe.add_argument("--output")
    openaip_probe.set_defaults(func=_run_openaip_png_probe)

    openaip_full = sub.add_parser("openaip-png-full", help="Create full OpenAIP PNG mosaic")
    openaip_full.add_argument("--zoom", type=int, required=True, choices=range(OPENAIP_MIN_ZOOM, OPENAIP_MAX_ZOOM + 1))
    openaip_full.add_argument("--start-x", type=int, required=True)
    openaip_full.add_argument("--start-y", type=int, required=True)
    openaip_full.add_argument("--layer", choices=["openaip", "hotspots"], default="openaip")
    openaip_full.add_argument("--api-key")
    openaip_full.add_argument("--max-search", type=int, default=50)
    openaip_full.add_argument("--timeout", type=float, default=15.0)
    openaip_full.add_argument("--output", default="openaip_png_full.png")
    openaip_full.add_argument("--no-progress", action="store_true")
    openaip_full.set_defaults(func=_run_openaip_png_full)

    openaip_composite = sub.add_parser(
        "openaip-composite-full",
        help="Create OpenAIP overlay combined with ESRI basemap for region context",
    )
    openaip_composite.add_argument("--zoom", type=int, required=True, choices=range(OPENAIP_MIN_ZOOM, OPENAIP_MAX_ZOOM + 1))
    openaip_composite.add_argument("--start-x", type=int, required=True)
    openaip_composite.add_argument("--start-y", type=int, required=True)
    openaip_composite.add_argument("--layer", choices=["openaip", "hotspots"], default="openaip")
    openaip_composite.add_argument("--api-key")
    openaip_composite.add_argument("--basemap", default="World_Topo_Map")
    openaip_composite.add_argument("--overlay-alpha", type=int, default=220)
    openaip_composite.add_argument("--white-threshold", type=int, default=248)
    openaip_composite.add_argument("--max-search", type=int, default=50)
    openaip_composite.add_argument("--timeout", type=float, default=15.0)
    openaip_composite.add_argument("--output", default="openaip_composite_full.png")
    openaip_composite.add_argument("--no-progress", action="store_true")
    openaip_composite.set_defaults(func=_run_openaip_composite_full)

    openaip_style = sub.add_parser("openaip-style", help="Fetch an OpenAIP style JSON")
    openaip_style.add_argument("--style", choices=["openaip-default-style", "openaip-satellite-style"], required=True)
    openaip_style.add_argument("--output")
    openaip_style.add_argument("--timeout", type=float, default=10.0)
    openaip_style.set_defaults(func=_run_openaip_style)

    latlon = sub.add_parser("latlon-to-tile", help="Convert lat/lon to XYZ tile coordinates")
    latlon.add_argument("--lat", type=float, required=True)
    latlon.add_argument("--lon", type=float, required=True)
    latlon.add_argument("--zoom", type=int, required=True, choices=range(OPENAIP_MIN_ZOOM, OPENAIP_MAX_ZOOM + 1))
    latlon.set_defaults(func=_run_latlon_to_tile)

    bbox = sub.add_parser("bbox-to-tiles", help="Convert lat/lon bbox to tile bounds and center suggestion")
    bbox.add_argument("--lat-min", type=float, required=True)
    bbox.add_argument("--lon-min", type=float, required=True)
    bbox.add_argument("--lat-max", type=float, required=True)
    bbox.add_argument("--lon-max", type=float, required=True)
    bbox.add_argument("--zoom", type=int, required=True, choices=range(OPENAIP_MIN_ZOOM, OPENAIP_MAX_ZOOM + 1))
    bbox.set_defaults(func=_run_bbox_to_tiles)

    vector_grid = sub.add_parser("openaip-vector-grid", help="Render OpenAIP vector tiles with selectable layers")
    vector_grid.add_argument("--zoom", type=int, required=True, choices=range(OPENAIP_MIN_ZOOM, OPENAIP_MAX_ZOOM + 1))
    vector_grid.add_argument("--start-x", type=int, required=True)
    vector_grid.add_argument("--start-y", type=int, required=True)
    vector_grid.add_argument("--width", type=int, default=2)
    vector_grid.add_argument("--height", type=int, default=2)
    vector_grid.add_argument("--tile-size", type=int, default=512)
    vector_grid.add_argument("--layers")
    vector_grid.add_argument("--api-key")
    vector_grid.add_argument("--output", default="openaip_vector_grid.png")
    vector_grid.set_defaults(func=_run_openaip_vector_grid)

    crop_percent = sub.add_parser("crop-percent", help="Crop image by percentages")
    crop_percent.add_argument("--image", required=True)
    crop_percent.add_argument("--center-x-pct", type=float, default=50.0)
    crop_percent.add_argument("--center-y-pct", type=float, default=50.0)
    crop_percent.add_argument("--width-pct", type=float, default=25.0)
    crop_percent.add_argument("--height-pct", type=float, default=25.0)
    crop_percent.add_argument("--output")
    crop_percent.set_defaults(func=_run_crop_percent)

    crop_regions_cmd = sub.add_parser("crop-regions", help="Crop image by explicit regions")
    crop_regions_cmd.add_argument("--image", required=True)
    crop_regions_cmd.add_argument("--regions", required=True, type=_parse_regions)
    crop_regions_cmd.add_argument("--output-prefix", default="cropped")
    crop_regions_cmd.set_defaults(func=_run_crop_regions)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
