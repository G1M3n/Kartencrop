from __future__ import annotations

from typing import Iterable, Sequence

from PIL import Image, ImageDraw


LAYER_COLORS: dict[str, tuple[int, int, int, int]] = {
    "airports": (30, 70, 180, 255),
    "airspaces": (180, 40, 40, 220),
    "airspaces_border_offset": (200, 80, 80, 200),
    "airspaces_border_offset_2x": (220, 120, 120, 180),
    "navaids": (30, 140, 60, 255),
    "reporting_points": (170, 120, 10, 255),
    "obstacles": (80, 50, 20, 255),
    "rc_airfields": (120, 40, 150, 255),
}


def decode_vector_tile(payload: bytes) -> dict:
    try:
        import mapbox_vector_tile
    except ImportError as exc:
        raise RuntimeError("install mapbox-vector-tile to decode .pbf tiles") from exc
    return mapbox_vector_tile.decode(payload, default_options={"y_coord_down": True})


def _scale_point(x: float, y: float, scale: float) -> tuple[float, float]:
    return x * scale, y * scale


def _draw_line(draw: ImageDraw.ImageDraw, points: Iterable[tuple[float, float]], color: tuple[int, int, int, int]) -> None:
    pts = list(points)
    if len(pts) >= 2:
        draw.line(pts, fill=color, width=2)


def _draw_polygon(draw: ImageDraw.ImageDraw, ring: Iterable[tuple[float, float]], color: tuple[int, int, int, int]) -> None:
    pts = list(ring)
    if len(pts) >= 3:
        draw.polygon(pts, outline=color, fill=(color[0], color[1], color[2], 60))


def render_vector_tile(
    tile_data: dict,
    tile_size: int = 768,
    extent: int = 4096,
    enabled_layers: Sequence[str] | None = None,
) -> Image.Image:
    img = Image.new("RGBA", (tile_size, tile_size), color=(245, 248, 252, 255))
    draw = ImageDraw.Draw(img, "RGBA")

    enabled = set(enabled_layers) if enabled_layers else None

    for layer_name, layer in tile_data.items():
        if enabled is not None and layer_name not in enabled:
            continue
        layer_extent = int(layer.get("extent", extent) or extent)
        scale = tile_size / layer_extent
        color = LAYER_COLORS.get(layer_name, (80, 80, 80, 255))
        for feature in layer.get("features", []):
            geometry = feature.get("geometry", {})
            geom_type = geometry.get("type")
            coords = geometry.get("coordinates")
            if not coords:
                continue

            if geom_type == "Point":
                x, y = coords
                px, py = _scale_point(x, y, scale)
                r = 3
                draw.ellipse((px - r, py - r, px + r, py + r), fill=color)
            elif geom_type == "MultiPoint":
                for x, y in coords:
                    px, py = _scale_point(x, y, scale)
                    r = 2
                    draw.ellipse((px - r, py - r, px + r, py + r), fill=color)
            elif geom_type == "LineString":
                _draw_line(draw, (_scale_point(x, y, scale) for x, y in coords), color)
            elif geom_type == "MultiLineString":
                for line in coords:
                    _draw_line(draw, (_scale_point(x, y, scale) for x, y in line), color)
            elif geom_type == "Polygon":
                for ring in coords:
                    _draw_polygon(draw, (_scale_point(x, y, scale) for x, y in ring), color)
            elif geom_type == "MultiPolygon":
                for polygon in coords:
                    for ring in polygon:
                        _draw_polygon(draw, (_scale_point(x, y, scale) for x, y in ring), color)

    return img.convert("RGB")
