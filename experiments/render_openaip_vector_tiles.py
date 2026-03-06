from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from kartencrop.openaip import fetch_vector_tile, openaip_session
from kartencrop.openaip_render import decode_vector_tile, render_vector_tile


def render_single(
    z: int,
    x: int,
    y: int,
    tile_size: int = 768,
    output: str | None = None,
    enabled_layers: list[str] | None = None,
) -> None:
    session = openaip_session()
    result = fetch_vector_tile(z=z, x=x, y=y, session=session)
    print(f"status={result.status_code} size={len(result.content)}")
    if not result.ok:
        return

    tile_data = decode_vector_tile(result.content)
    for name, layer in tile_data.items():
        print(f"{name}: {len(layer.get('features', []))} features")

    image = render_vector_tile(tile_data, tile_size=tile_size, enabled_layers=enabled_layers)
    out = Path(output or f"openaip_single_tile_z{z}_x{x}_y{y}.png")
    image.save(out)
    print(f"saved: {out}")


def render_grid(
    z: int,
    start_x: int,
    start_y: int,
    width: int,
    height: int,
    tile_size: int = 768,
    output: str = "openaip_grid.png",
    enabled_layers: list[str] | None = None,
) -> None:
    session = openaip_session()
    canvas = Image.new("RGB", (width * tile_size, height * tile_size), color=(245, 248, 252))
    loaded = 0
    total = width * height

    for gy in range(height):
        for gx in range(width):
            x = start_x + gx
            y = start_y + gy
            result = fetch_vector_tile(z=z, x=x, y=y, session=session)
            if not result.ok:
                print(f"missing z{z}/{x}/{y} status={result.status_code}")
                continue

            tile_data = decode_vector_tile(result.content)
            tile_img = render_vector_tile(tile_data, tile_size=tile_size, enabled_layers=enabled_layers)
            canvas.paste(tile_img, (gx * tile_size, gy * tile_size))
            loaded += 1
            print(f"loaded z{z}/{x}/{y}")

    out = Path(output)
    canvas.save(out)
    print(f"saved: {out} ({canvas.width}x{canvas.height})")
    print(f"tiles: {loaded}/{total}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render OpenAIP vector tiles")
    parser.add_argument("--z", type=int, default=5)
    parser.add_argument("--x", type=int, default=16)
    parser.add_argument("--y", type=int, default=12)
    parser.add_argument("--width", type=int, default=1)
    parser.add_argument("--height", type=int, default=1)
    parser.add_argument("--tile-size", type=int, default=768)
    parser.add_argument("--output")
    parser.add_argument(
        "--layers",
        help="comma-separated list, e.g. airports,airspaces,navaids,reporting_points,obstacles,rc_airfields",
    )
    args = parser.parse_args()
    layers = [x.strip() for x in args.layers.split(",")] if args.layers else None

    if args.width == 1 and args.height == 1:
        render_single(args.z, args.x, args.y, tile_size=args.tile_size, output=args.output, enabled_layers=layers)
        return 0

    output = args.output or f"openaip_grid_z{args.z}_x{args.x}_y{args.y}_{args.width}x{args.height}.png"
    render_grid(
        z=args.z,
        start_x=args.x,
        start_y=args.y,
        width=args.width,
        height=args.height,
        tile_size=args.tile_size,
        output=output,
        enabled_layers=layers,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
