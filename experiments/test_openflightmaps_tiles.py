from __future__ import annotations

from kartencrop.providers import OpenFlightMapsProvider


def smoke_test_tiles() -> None:
    provider = OpenFlightMapsProvider(zoom=8, cycle="latest")
    coords = [(140, 72), (144, 72), (145, 72)]

    for x, y in coords:
        img = provider.fetch_tile(x, y)
        if img is None:
            print(f"missing tile z8/{x}/{y}")
            continue
        out = f"openflightmaps_tile_z8_x{x}_y{y}.png"
        img.save(out)
        print(f"ok z8/{x}/{y} -> {out}")


if __name__ == "__main__":
    smoke_test_tiles()
