from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from PIL import Image


@dataclass(frozen=True)
class CropBox:
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1


def validate_crop_box(box: CropBox, image_width: int, image_height: int) -> None:
    if box.x1 < 0 or box.y1 < 0:
        raise ValueError("Crop coordinates must be >= 0")
    if box.x2 > image_width or box.y2 > image_height:
        raise ValueError("Crop coordinates exceed image dimensions")
    if box.x1 >= box.x2 or box.y1 >= box.y2:
        raise ValueError("Crop box must have positive width and height")


def crop_by_percentage(
    image: Image.Image,
    center_x_pct: float = 50.0,
    center_y_pct: float = 50.0,
    width_pct: float = 25.0,
    height_pct: float = 25.0,
) -> tuple[Image.Image, CropBox]:
    image_width, image_height = image.size

    center_x = int(image_width * center_x_pct / 100)
    center_y = int(image_height * center_y_pct / 100)
    crop_width = int(image_width * width_pct / 100)
    crop_height = int(image_height * height_pct / 100)

    x1 = max(0, center_x - crop_width // 2)
    y1 = max(0, center_y - crop_height // 2)
    x2 = min(image_width, x1 + crop_width)
    y2 = min(image_height, y1 + crop_height)

    box = CropBox(x1=x1, y1=y1, x2=x2, y2=y2)
    validate_crop_box(box, image_width=image_width, image_height=image_height)

    return image.crop((box.x1, box.y1, box.x2, box.y2)), box


def crop_regions(image: Image.Image, boxes: Iterable[CropBox]) -> List[tuple[CropBox, Image.Image]]:
    image_width, image_height = image.size
    results: List[tuple[CropBox, Image.Image]] = []

    for box in boxes:
        validate_crop_box(box, image_width=image_width, image_height=image_height)
        cropped = image.crop((box.x1, box.y1, box.x2, box.y2))
        results.append((box, cropped))

    return results


def save_cropped_regions(
    crops: Iterable[tuple[CropBox, Image.Image]],
    output_prefix: str,
    quality: int = 95,
) -> list[str]:
    output_paths: list[str] = []

    for idx, (box, image) in enumerate(crops, start=1):
        target = Path(f"{output_prefix}_region{idx}_{box.x1}_{box.y1}_{box.x2}_{box.y2}.jpg")
        image.save(target, format="JPEG", quality=quality)
        output_paths.append(str(target))

    return output_paths
