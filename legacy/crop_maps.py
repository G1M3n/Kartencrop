from __future__ import annotations

import argparse
from typing import Iterable

from PIL import Image

from kartencrop.crop import CropBox, crop_by_percentage, crop_regions, save_cropped_regions


Image.MAX_IMAGE_PIXELS = None


def crop_map_interactive(
    image_path: str,
    crop_regions_input: list[tuple[int, int, int, int]] | None = None,
    output_prefix: str = "cropped",
):
    image = Image.open(image_path)
    if crop_regions_input is None:
        width, height = image.size
        crop_regions_input = [
            (int(width * 0.25), int(height * 0.25), int(width * 0.75), int(height * 0.75)),
            (0, 0, int(width * 0.25), int(height * 0.25)),
            (int(width * 0.75), int(height * 0.75), width, height),
        ]

    boxes = [CropBox(*coords) for coords in crop_regions_input]
    crops = crop_regions(image=image, boxes=boxes)
    paths = save_cropped_regions(crops=crops, output_prefix=output_prefix)

    return [
        {
            "region": idx,
            "coords": (box.x1, box.y1, box.x2, box.y2),
            "path": path,
        }
        for idx, ((box, _), path) in enumerate(zip(crops, paths), start=1)
    ]


def crop_map_by_percentage(
    image_path: str,
    center_x_pct: float = 50,
    center_y_pct: float = 50,
    width_pct: float = 25,
    height_pct: float = 25,
    output_path: str | None = None,
):
    image = Image.open(image_path)
    cropped, box = crop_by_percentage(
        image=image,
        center_x_pct=center_x_pct,
        center_y_pct=center_y_pct,
        width_pct=width_pct,
        height_pct=height_pct,
    )

    if output_path is None:
        output_path = (
            f"{image_path.rsplit('.', 1)[0]}_crop_center{int(center_x_pct)}_{int(center_y_pct)}"
            f"_size{int(width_pct)}x{int(height_pct)}.jpg"
        )

    cropped.save(output_path, format="JPEG", quality=95)
    return cropped, (box.x1, box.y1, box.x2, box.y2)


def _parse_regions(regions: str) -> list[tuple[int, int, int, int]]:
    parsed: list[tuple[int, int, int, int]] = []
    for part in regions.split(";"):
        x1, y1, x2, y2 = (int(v.strip()) for v in part.split(","))
        parsed.append((x1, y1, x2, y2))
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description="Crop utility")
    parser.add_argument("--image", required=True)
    parser.add_argument("--mode", choices=["percent", "regions"], default="percent")
    parser.add_argument("--center-x-pct", type=float, default=50.0)
    parser.add_argument("--center-y-pct", type=float, default=50.0)
    parser.add_argument("--width-pct", type=float, default=25.0)
    parser.add_argument("--height-pct", type=float, default=25.0)
    parser.add_argument("--regions", help="x1,y1,x2,y2;x1,y1,x2,y2")
    parser.add_argument("--output")
    parser.add_argument("--output-prefix", default="cropped")
    args = parser.parse_args()

    if args.mode == "percent":
        _, coords = crop_map_by_percentage(
            image_path=args.image,
            center_x_pct=args.center_x_pct,
            center_y_pct=args.center_y_pct,
            width_pct=args.width_pct,
            height_pct=args.height_pct,
            output_path=args.output,
        )
        print(f"crop: {coords}")
        return 0

    if not args.regions:
        raise ValueError("--regions is required for mode=regions")

    results = crop_map_interactive(
        image_path=args.image,
        crop_regions_input=_parse_regions(args.regions),
        output_prefix=args.output_prefix,
    )
    print(f"created {len(results)} crops")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
