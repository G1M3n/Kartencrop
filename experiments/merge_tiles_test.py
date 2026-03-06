from __future__ import annotations

from PIL import Image

from kartencrop.providers import GeoPfProvider
from kartencrop.tiles import Bounds, stitch_tiles


def merge_two_tiles(tilematrix: str = "11", row: int = 721, col_left: int = 1025) -> Image.Image:
    provider = GeoPfProvider(tilematrix=tilematrix)
    bounds = Bounds(min_x=col_left, max_x=col_left + 1, min_y=row, max_y=row)
    mosaic = stitch_tiles(fetch_tile=provider.fetch_tile, bounds=bounds, show_progress=False)
    return mosaic.image


if __name__ == "__main__":
    image = merge_two_tiles()
    output = "merged_test_horizontal.jpg"
    image.save(output, format="JPEG", quality=95)
    print(f"saved: {output} ({image.width}x{image.height})")
