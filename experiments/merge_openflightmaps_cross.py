from __future__ import annotations

from PIL import Image, ImageDraw

from kartencrop.providers import OpenFlightMapsProvider


def merge_tiles_cross(center_z: int, center_x: int, center_y: int, cycle: str = "latest") -> Image.Image:
    provider = OpenFlightMapsProvider(zoom=center_z, cycle=cycle)
    positions = {
        "top": (center_x, center_y - 1),
        "left": (center_x - 1, center_y),
        "center": (center_x, center_y),
        "right": (center_x + 1, center_y),
        "bottom": (center_x, center_y + 1),
    }

    tiles = {name: provider.fetch_tile(x, y) for name, (x, y) in positions.items()}
    available = [img for img in tiles.values() if img is not None]
    if not available:
        raise ValueError("no tiles loaded")

    tile_size = available[0].size[0]
    merged = Image.new("RGB", (3 * tile_size, 3 * tile_size), color=(240, 240, 240))
    layout = {
        "top": (tile_size, 0),
        "left": (0, tile_size),
        "center": (tile_size, tile_size),
        "right": (2 * tile_size, tile_size),
        "bottom": (tile_size, 2 * tile_size),
    }
    for name, pos in layout.items():
        if tiles[name] is not None:
            merged.paste(tiles[name], pos)

    draw = ImageDraw.Draw(merged)
    for name, (x, y) in positions.items():
        if tiles[name] is None:
            continue
        lx, ly = layout[name]
        draw.rectangle((lx + 4, ly + 4, lx + 150, ly + 42), fill=(255, 255, 255))
        draw.text((lx + 8, ly + 8), f"{name}: {x},{y}", fill=(0, 0, 0))

    return merged


if __name__ == "__main__":
    img = merge_tiles_cross(center_z=8, center_x=144, center_y=72)
    out = "openflightmaps_cross_z8_x144_y72.jpg"
    img.save(out, format="JPEG", quality=95)
    print(f"saved: {out}")
