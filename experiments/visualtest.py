from __future__ import annotations

from kartencrop.providers import GeoPfProvider


def main() -> None:
    provider = GeoPfProvider(tilematrix="11")
    image = provider.fetch_tile(1027, 720)
    if image is None:
        raise SystemExit("tile not found")

    out = "wmts_tile_11_1027_720.jpg"
    image.save(out, format="JPEG", quality=95)
    print(f"saved: {out} ({image.width}x{image.height})")


if __name__ == "__main__":
    main()
