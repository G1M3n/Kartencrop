from pathlib import Path
import shutil
import uuid

from PIL import Image

from kartencrop.cache import cached_tile_fetch
from kartencrop.crop import CropBox, crop_by_percentage, crop_regions
from kartencrop.tiles import (
    Bounds,
    clip_bounds,
    find_bounds,
    find_connected_bounds,
    find_nearest_valid_tile,
    memoize_fetch_tile,
    render_composite_tiles_to_output,
    render_tiles_to_output,
)


def test_bounds_dimensions() -> None:
    bounds = Bounds(min_x=10, max_x=12, min_y=20, max_y=24)
    assert bounds.width == 3
    assert bounds.height == 5


def test_clip_bounds_intersects_ranges() -> None:
    bounds = Bounds(min_x=10, max_x=20, min_y=30, max_y=40)
    clipped = clip_bounds(bounds, min_x=15, max_x=18, min_y=32, max_y=50)
    assert clipped == Bounds(min_x=15, max_x=18, min_y=32, max_y=40)


def test_clip_bounds_returns_none_without_overlap() -> None:
    bounds = Bounds(min_x=10, max_x=20, min_y=30, max_y=40)
    assert clip_bounds(bounds, min_x=21, max_x=25, min_y=30, max_y=40) is None


def test_find_bounds_expands_until_missing_tile() -> None:
    existing = {(x, y) for x in range(9, 13) for y in range(19, 23)}

    def fetch_tile(x: int, y: int):
        return object() if (x, y) in existing else None

    bounds = find_bounds(fetch_tile=fetch_tile, start_x=10, start_y=20, max_search=10)
    assert bounds.min_x == 9
    assert bounds.max_x == 12
    assert bounds.min_y == 19
    assert bounds.max_y == 22


def test_find_nearest_valid_tile_returns_closest_hit() -> None:
    existing = {(10, 10), (12, 11), (9, 13)}

    def fetch_tile(x: int, y: int):
        return object() if (x, y) in existing else None

    assert find_nearest_valid_tile(fetch_tile=fetch_tile, start_x=11, start_y=10, max_distance=2) == (10, 10)


def test_find_connected_bounds_captures_irregular_component() -> None:
    existing = {
        (10, 10),
        (11, 10),
        (12, 10),
        (10, 11),
        (12, 11),
        (12, 12),
    }

    def fetch_tile(x: int, y: int):
        return object() if (x, y) in existing else None

    bounds = find_connected_bounds(fetch_tile=fetch_tile, start_x=10, start_y=10, max_search=5)
    assert bounds.min_x == 10
    assert bounds.max_x == 12
    assert bounds.min_y == 10
    assert bounds.max_y == 12


def test_memoize_fetch_tile_only_calls_source_once_per_coordinate() -> None:
    calls: list[tuple[int, int]] = []

    def fetch_tile(x: int, y: int):
        calls.append((x, y))
        return object()

    cached = memoize_fetch_tile(fetch_tile)
    cached(1, 2)
    cached(1, 2)
    cached(2, 3)
    assert calls == [(1, 2), (2, 3)]


def test_cached_tile_fetch_persists_tiles_on_disk() -> None:
    calls: list[tuple[int, int]] = []

    def fetch_tile(x: int, y: int):
        calls.append((x, y))
        return Image.new("RGB", (4, 4), (x, y, 0))

    tmp_path = Path.cwd() / "outputs" / "test_cache" / f"case_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    try:
        cached = cached_tile_fetch(fetch_tile, namespace="tests/provider", cache_dir=tmp_path)
        image_a = cached(1, 2)
        image_b = cached(1, 2)

        assert image_a is not None
        assert image_b is not None
        assert calls == [(1, 2)]
        assert any(tmp_path.rglob("1_2.png"))
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_cached_tile_fetch_persists_missing_tiles_on_disk() -> None:
    calls: list[tuple[int, int]] = []

    def fetch_tile(x: int, y: int):
        calls.append((x, y))
        return None

    tmp_path = Path.cwd() / "outputs" / "test_cache" / f"case_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    try:
        cached = cached_tile_fetch(fetch_tile, namespace="tests/provider", cache_dir=tmp_path)

        assert cached(9, 9) is None
        assert cached(9, 9) is None
        assert calls == [(9, 9)]
        assert any(tmp_path.rglob("9_9.none"))
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_crop_by_percentage() -> None:
    image = Image.new("RGB", (1000, 600), (255, 255, 255))
    _, box = crop_by_percentage(
        image=image,
        center_x_pct=50,
        center_y_pct=50,
        width_pct=20,
        height_pct=50,
    )
    assert box == CropBox(x1=400, y1=150, x2=600, y2=450)


def test_crop_regions() -> None:
    image = Image.new("RGB", (300, 300), (255, 255, 255))
    boxes = [CropBox(0, 0, 100, 100), CropBox(50, 50, 120, 180)]
    crops = crop_regions(image=image, boxes=boxes)

    assert len(crops) == 2
    assert crops[0][1].size == (100, 100)
    assert crops[1][1].size == (70, 130)


def test_render_tiles_to_output_uses_low_memory_canvas() -> None:
    colors = {
        (0, 0): (255, 0, 0),
        (1, 0): (0, 255, 0),
        (0, 1): (0, 0, 255),
        (1, 1): (255, 255, 0),
    }

    def fetch_tile(x: int, y: int):
        color = colors.get((x, y))
        if color is None:
            return None
        return Image.new("RGB", (8, 8), color)

    tmp_path = Path.cwd() / "outputs" / "test_cache" / f"case_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    output = tmp_path / "low_memory_render.png"
    try:
        result = render_tiles_to_output(
            fetch_tile=fetch_tile,
            bounds=Bounds(min_x=0, max_x=1, min_y=0, max_y=1),
            output_path=output,
            show_progress=False,
            preview_width=8,
            force_low_memory=True,
        )

        assert result.used_low_memory is True
        assert output.exists()
        assert result.preview_path.exists()
        with Image.open(output) as image:
            assert image.size == (16, 16)
            assert image.getpixel((4, 4))[:3] == (255, 0, 0)
            assert image.getpixel((12, 4))[:3] == (0, 255, 0)
            assert image.getpixel((4, 12))[:3] == (0, 0, 255)
            assert image.getpixel((12, 12))[:3] == (255, 255, 0)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_render_composite_tiles_to_output_uses_low_memory_canvas() -> None:
    def base_fetch_tile(x: int, y: int):
        if x not in {0, 1} or y not in {0, 1}:
            return None
        return Image.new("RGB", (8, 8), (20, 40, 60))

    def overlay_fetch_tile(x: int, y: int):
        if x not in {0, 1} or y not in {0, 1}:
            return None
        return Image.new("RGBA", (8, 8), (255, 0, 0, 128))

    tmp_path = Path.cwd() / "outputs" / "test_cache" / f"case_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    output = tmp_path / "low_memory_composite.png"
    try:
        result = render_composite_tiles_to_output(
            base_fetch_tile=base_fetch_tile,
            overlay_fetch_tile=overlay_fetch_tile,
            bounds=Bounds(min_x=0, max_x=1, min_y=0, max_y=1),
            output_path=output,
            show_progress=False,
            preview_width=8,
            force_low_memory=True,
        )

        assert result.used_low_memory is True
        assert result.base_loaded_tiles == 4
        assert result.overlay_loaded_tiles == 4
        assert output.exists()
        assert result.preview_path.exists()
        with Image.open(output) as image:
            pixel = image.convert("RGB").getpixel((4, 4))
            assert pixel[0] > 20
            assert pixel[1] < 40
            assert pixel[2] < 60
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
