from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import mmap
import os
from pathlib import Path
import tempfile
from typing import BinaryIO, Callable, Iterator, Optional

from PIL import Image

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    tqdm = None


FetchTileFn = Callable[[int, int], Optional[Image.Image]]
ProgressCallback = Callable[[int, int], None]
TileTransformFn = Callable[[Image.Image], Image.Image]

# Roughly 96 MB for RGBA backing storage. Above this, the renderer spills the
# canvas to a disk-backed mmap instead of relying on process RAM only.
LOW_MEMORY_PIXEL_THRESHOLD = 24_000_000


@dataclass(frozen=True)
class Bounds:
    min_x: int
    max_x: int
    min_y: int
    max_y: int

    @property
    def width(self) -> int:
        return self.max_x - self.min_x + 1

    @property
    def height(self) -> int:
        return self.max_y - self.min_y + 1


@dataclass(frozen=True)
class MosaicResult:
    image: Image.Image
    loaded_tiles: int
    total_tiles: int
    tile_width: int
    tile_height: int


@dataclass(frozen=True)
class BuildResult:
    bounds: Bounds
    mosaic: MosaicResult


@dataclass(frozen=True)
class SavedRenderResult:
    output_path: Path
    preview_path: Path
    loaded_tiles: int
    total_tiles: int
    tile_width: int
    tile_height: int
    used_low_memory: bool


@dataclass(frozen=True)
class SavedCompositeRenderResult:
    output_path: Path
    preview_path: Path
    base_loaded_tiles: int
    overlay_loaded_tiles: int
    total_tiles: int
    tile_width: int
    tile_height: int
    used_low_memory: bool


def clip_bounds(
    bounds: Bounds,
    *,
    min_x: int,
    max_x: int,
    min_y: int,
    max_y: int,
) -> Bounds | None:
    clipped_min_x = max(bounds.min_x, min_x)
    clipped_max_x = min(bounds.max_x, max_x)
    clipped_min_y = max(bounds.min_y, min_y)
    clipped_max_y = min(bounds.max_y, max_y)
    if clipped_min_x > clipped_max_x or clipped_min_y > clipped_max_y:
        return None
    return Bounds(
        min_x=clipped_min_x,
        max_x=clipped_max_x,
        min_y=clipped_min_y,
        max_y=clipped_max_y,
    )


def memoize_fetch_tile(fetch_tile: FetchTileFn) -> FetchTileFn:
    cache: dict[tuple[int, int], Optional[Image.Image]] = {}

    def cached_fetch(x: int, y: int) -> Optional[Image.Image]:
        key = (x, y)
        if key not in cache:
            cache[key] = fetch_tile(x, y)
        return cache[key]

    return cached_fetch


def _image_has_alpha(image: Image.Image) -> bool:
    return image.mode in {"RGBA", "LA"}


def _paste_tile(canvas: Image.Image, tile: Image.Image, px: int, py: int) -> None:
    if _image_has_alpha(tile):
        tile_rgba = tile.convert("RGBA")
        canvas.paste(tile_rgba, (px, py), tile_rgba)
        return
    canvas.paste(tile, (px, py))


def _flatten_for_jpeg(image: Image.Image) -> Image.Image:
    if not _image_has_alpha(image):
        return image.convert("RGB")
    rgba = image.convert("RGBA")
    background = Image.new("RGB", rgba.size, (255, 255, 255))
    background.paste(rgba, mask=rgba.getchannel("A"))
    return background


def _first_available_tile(
    fetch_tile: FetchTileFn,
    bounds: Bounds,
) -> tuple[Image.Image | None, tuple[int, int] | None]:
    for y in range(bounds.min_y, bounds.max_y + 1):
        for x in range(bounds.min_x, bounds.max_x + 1):
            tile = fetch_tile(x, y)
            if tile is not None:
                return tile, (x, y)
    return None, None


def _temporary_canvas_dir() -> Path:
    path = Path.cwd() / "outputs" / "cache" / "tmp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _mode_background(mode: str, background: tuple[int, ...]) -> tuple[int, ...]:
    if mode == "RGBA":
        if len(background) == 4:
            return background
        return (*background[:3], 0)
    return background[:3]


def _fill_backing_store(buffer: mmap.mmap, pattern: bytes, total_bytes: int) -> None:
    if not pattern:
        return
    if pattern == b"\x00" * len(pattern):
        return

    chunk_size = max(len(pattern), (1024 * 1024 // len(pattern)) * len(pattern))
    chunk = pattern * (chunk_size // len(pattern))
    offset = 0
    while offset < total_bytes:
        remaining = total_bytes - offset
        data = chunk if remaining >= len(chunk) else chunk[:remaining]
        buffer[offset : offset + len(data)] = data
        offset += len(data)


class _CanvasSurface:
    def __init__(
        self,
        *,
        mode: str,
        size: tuple[int, int],
        background: tuple[int, ...],
        use_low_memory: bool,
    ) -> None:
        self.mode = mode
        self.size = size
        self.used_low_memory = use_low_memory
        self.image: Image.Image
        self._backing_path: Path | None = None
        self._backing_file: BinaryIO | None = None
        self._backing_map: mmap.mmap | None = None

        if not use_low_memory:
            self.image = Image.new(mode, size, _mode_background(mode, background))
            return

        channels = len(mode)
        total_bytes = size[0] * size[1] * channels
        temp_dir = _temporary_canvas_dir()
        fd, raw_path = tempfile.mkstemp(prefix="kartencrop_canvas_", suffix=".raw", dir=temp_dir)
        self._backing_path = Path(raw_path)
        self._backing_file = os.fdopen(fd, "w+b")
        self._backing_file.truncate(total_bytes)
        self._backing_file.flush()
        self._backing_map = mmap.mmap(self._backing_file.fileno(), total_bytes, access=mmap.ACCESS_WRITE)
        _fill_backing_store(
            self._backing_map,
            bytes(_mode_background(mode, background)),
            total_bytes,
        )
        self.image = Image.frombuffer(mode, size, self._backing_map, "raw", mode, 0, 1)
        try:
            self.image.readonly = False
        except Exception:  # pragma: no cover
            pass

    def close(self) -> None:
        self.image = None  # type: ignore[assignment]
        if self._backing_map is not None:
            self._backing_map.flush()
            self._backing_map.close()
            self._backing_map = None
        if self._backing_file is not None:
            self._backing_file.close()
            self._backing_file = None
        if self._backing_path is not None and self._backing_path.exists():
            try:
                self._backing_path.unlink()
            except OSError:  # pragma: no cover
                pass

    def __enter__(self) -> _CanvasSurface:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def _range_with_optional_progress(values: Iterator[tuple[int, int]], total: int, show_progress: bool, desc: str):
    if show_progress and tqdm is not None:
        return tqdm(values, total=total, desc=desc)
    return values


def find_bounds(fetch_tile: FetchTileFn, start_x: int, start_y: int, max_search: int = 50) -> Bounds:
    min_x = start_x
    max_x = start_x
    min_y = start_y
    max_y = start_y

    for x in range(start_x - 1, start_x - max_search - 1, -1):
        if fetch_tile(x, start_y) is None:
            break
        min_x = x

    for x in range(start_x + 1, start_x + max_search + 1):
        if fetch_tile(x, start_y) is None:
            break
        max_x = x

    for y in range(start_y - 1, start_y - max_search - 1, -1):
        if fetch_tile(start_x, y) is None:
            break
        min_y = y

    for y in range(start_y + 1, start_y + max_search + 1):
        if fetch_tile(start_x, y) is None:
            break
        max_y = y

    return Bounds(min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y)


def find_nearest_valid_tile(
    fetch_tile: FetchTileFn,
    start_x: int,
    start_y: int,
    max_distance: int = 0,
) -> tuple[int, int] | None:
    if fetch_tile(start_x, start_y) is not None:
        return start_x, start_y

    for distance in range(1, max_distance + 1):
        hits: list[tuple[int, int, int, int]] = []
        for dy in range(-distance, distance + 1):
            for dx in range(-distance, distance + 1):
                if max(abs(dx), abs(dy)) != distance:
                    continue
                x = start_x + dx
                y = start_y + dy
                if fetch_tile(x, y) is None:
                    continue
                hits.append((abs(dx) + abs(dy), abs(dy), abs(dx), x, y))
        if hits:
            hits.sort()
            _, _, _, x, y = hits[0]
            return x, y
    return None


def find_connected_tiles(
    fetch_tile: FetchTileFn,
    start_x: int,
    start_y: int,
    max_search: int = 50,
) -> set[tuple[int, int]]:
    valid_tiles: set[tuple[int, int]] = set()
    queue = deque([(start_x, start_y)])
    seen = {(start_x, start_y)}
    min_x = start_x - max_search
    max_x = start_x + max_search
    min_y = start_y - max_search
    max_y = start_y + max_search

    while queue:
        x, y = queue.popleft()
        if x < min_x or x > max_x or y < min_y or y > max_y:
            continue
        if fetch_tile(x, y) is None:
            continue
        valid_tiles.add((x, y))
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if (nx, ny) in seen:
                continue
            seen.add((nx, ny))
            queue.append((nx, ny))
    return valid_tiles


def find_connected_bounds(
    fetch_tile: FetchTileFn,
    start_x: int,
    start_y: int,
    max_search: int = 50,
) -> Bounds:
    valid_tiles = find_connected_tiles(fetch_tile=fetch_tile, start_x=start_x, start_y=start_y, max_search=max_search)
    if not valid_tiles:
        raise ValueError("No tiles available in requested bounds")
    xs = [x for x, _ in valid_tiles]
    ys = [y for _, y in valid_tiles]
    return Bounds(min_x=min(xs), max_x=max(xs), min_y=min(ys), max_y=max(ys))


def stitch_tiles(
    fetch_tile: FetchTileFn,
    bounds: Bounds,
    background: tuple[int, int, int] = (255, 255, 255),
    show_progress: bool = True,
) -> MosaicResult:
    first_tile, first_coords = _first_available_tile(fetch_tile, bounds)
    if first_tile is None or first_coords is None:
        raise ValueError("No tiles available in requested bounds")

    tile_width, tile_height = first_tile.size
    total_tiles = bounds.width * bounds.height
    canvas_mode = "RGBA" if _image_has_alpha(first_tile) else "RGB"
    canvas_background = _mode_background(canvas_mode, background)
    image = Image.new(canvas_mode, (bounds.width * tile_width, bounds.height * tile_height), canvas_background)

    loaded_tiles = 0
    coords = (
        (x, y)
        for y in range(bounds.min_y, bounds.max_y + 1)
        for x in range(bounds.min_x, bounds.max_x + 1)
    )

    for x, y in _range_with_optional_progress(coords, total_tiles, show_progress, "loading tiles"):
        use_first = first_coords == (x, y)
        tile = first_tile if use_first else fetch_tile(x, y)
        if tile is None:
            continue

        px = (x - bounds.min_x) * tile_width
        py = (y - bounds.min_y) * tile_height
        _paste_tile(image, tile, px, py)
        loaded_tiles += 1

        if use_first:
            first_tile = None

    return MosaicResult(
        image=image,
        loaded_tiles=loaded_tiles,
        total_tiles=total_tiles,
        tile_width=tile_width,
        tile_height=tile_height,
    )


def _should_use_low_memory(width: int, height: int, force_low_memory: bool | None) -> bool:
    if force_low_memory is not None:
        return force_low_memory
    return width * height >= LOW_MEMORY_PIXEL_THRESHOLD


def _save_output_image(image: Image.Image, output_path: Path, quality: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_suffix = output_path.suffix.lower()
    if output_suffix == ".png":
        image.save(output_path, format="PNG")
        return
    _flatten_for_jpeg(image).save(output_path, format="JPEG", quality=quality)


def _create_preview_from_output(output_path: Path, preview_width: int, preview_quality: int) -> Path:
    preview_path = output_path.with_name(f"{output_path.stem}_preview{output_path.suffix}")
    with Image.open(output_path) as saved_image:
        effective_preview_width = min(preview_width, saved_image.width)
        preview_height = max(1, int(effective_preview_width * saved_image.height / saved_image.width))
        if effective_preview_width == saved_image.width:
            preview = saved_image.copy()
        else:
            preview = saved_image.resize((effective_preview_width, preview_height), Image.Resampling.LANCZOS)

    try:
        if output_path.suffix.lower() == ".png":
            preview.save(preview_path, format="PNG")
        else:
            _flatten_for_jpeg(preview).save(preview_path, format="JPEG", quality=preview_quality)
    finally:
        preview.close()
    return preview_path


def _build_progress_iterator(total_tiles: int, show_progress: bool, desc: str):
    if show_progress and tqdm is not None:
        return tqdm(total=total_tiles, desc=desc)
    return None


def _update_progress(
    *,
    progress_bar,
    progress_callback: ProgressCallback | None,
    processed_tiles: int,
    total_tiles: int,
) -> None:
    if progress_bar is not None:
        progress_bar.update(1)
    if progress_callback is not None:
        progress_callback(processed_tiles, total_tiles)


def render_tiles_to_output(
    *,
    fetch_tile: FetchTileFn,
    bounds: Bounds,
    output_path: str | Path,
    background: tuple[int, int, int] = (255, 255, 255),
    show_progress: bool = True,
    progress_callback: ProgressCallback | None = None,
    preview_width: int = 2000,
    quality: int = 95,
    preview_quality: int = 85,
    force_low_memory: bool | None = None,
) -> SavedRenderResult:
    first_tile, first_coords = _first_available_tile(fetch_tile, bounds)
    if first_tile is None or first_coords is None:
        raise ValueError("No tiles available in requested bounds")

    tile_width, tile_height = first_tile.size
    total_tiles = bounds.width * bounds.height
    canvas_mode = "RGBA" if _image_has_alpha(first_tile) else "RGB"
    canvas_background = _mode_background(canvas_mode, background)
    image_width = bounds.width * tile_width
    image_height = bounds.height * tile_height
    use_low_memory = _should_use_low_memory(image_width, image_height, force_low_memory)

    with _CanvasSurface(
        mode=canvas_mode,
        size=(image_width, image_height),
        background=canvas_background,
        use_low_memory=use_low_memory,
    ) as surface:
        loaded_tiles = 0
        processed_tiles = 0
        progress_bar = _build_progress_iterator(total_tiles, show_progress, "loading tiles")
        try:
            for y in range(bounds.min_y, bounds.max_y + 1):
                for x in range(bounds.min_x, bounds.max_x + 1):
                    use_first = first_coords == (x, y)
                    tile = first_tile if use_first else fetch_tile(x, y)
                    if tile is not None:
                        px = (x - bounds.min_x) * tile_width
                        py = (y - bounds.min_y) * tile_height
                        _paste_tile(surface.image, tile, px, py)
                        loaded_tiles += 1
                    if use_first:
                        first_tile = None
                    processed_tiles += 1
                    _update_progress(
                        progress_bar=progress_bar,
                        progress_callback=progress_callback,
                        processed_tiles=processed_tiles,
                        total_tiles=total_tiles,
                    )
        finally:
            if progress_bar is not None:
                progress_bar.close()

        output = Path(output_path)
        _save_output_image(surface.image, output, quality)
        preview = _create_preview_from_output(output, preview_width, preview_quality)

    return SavedRenderResult(
        output_path=output,
        preview_path=preview,
        loaded_tiles=loaded_tiles,
        total_tiles=total_tiles,
        tile_width=tile_width,
        tile_height=tile_height,
        used_low_memory=use_low_memory,
    )


def render_composite_tiles_to_output(
    *,
    base_fetch_tile: FetchTileFn,
    overlay_fetch_tile: FetchTileFn,
    bounds: Bounds,
    output_path: str | Path,
    background: tuple[int, int, int] = (255, 255, 255),
    show_progress: bool = True,
    progress_callback: ProgressCallback | None = None,
    preview_width: int = 2000,
    quality: int = 95,
    preview_quality: int = 85,
    overlay_transform: TileTransformFn | None = None,
    force_low_memory: bool | None = None,
) -> SavedCompositeRenderResult:
    first_base, first_base_coords = _first_available_tile(base_fetch_tile, bounds)
    first_overlay, first_overlay_coords = _first_available_tile(overlay_fetch_tile, bounds)
    seed_tile = first_base or first_overlay
    if seed_tile is None:
        raise ValueError("No tiles available in requested bounds")

    tile_width, tile_height = seed_tile.size
    total_tiles = bounds.width * bounds.height
    image_width = bounds.width * tile_width
    image_height = bounds.height * tile_height
    use_low_memory = _should_use_low_memory(image_width, image_height, force_low_memory)

    with _CanvasSurface(
        mode="RGBA",
        size=(image_width, image_height),
        background=_mode_background("RGBA", background),
        use_low_memory=use_low_memory,
    ) as surface:
        base_loaded_tiles = 0
        overlay_loaded_tiles = 0
        processed_tiles = 0
        progress_bar = _build_progress_iterator(total_tiles, show_progress, "loading tiles")
        try:
            for y in range(bounds.min_y, bounds.max_y + 1):
                for x in range(bounds.min_x, bounds.max_x + 1):
                    px = (x - bounds.min_x) * tile_width
                    py = (y - bounds.min_y) * tile_height

                    use_first_base = first_base_coords == (x, y)
                    base_tile = first_base if use_first_base else base_fetch_tile(x, y)
                    if base_tile is not None:
                        _paste_tile(surface.image, base_tile, px, py)
                        base_loaded_tiles += 1
                    if use_first_base:
                        first_base = None

                    use_first_overlay = first_overlay_coords == (x, y)
                    overlay_tile = first_overlay if use_first_overlay else overlay_fetch_tile(x, y)
                    if overlay_tile is not None:
                        if overlay_transform is not None:
                            overlay_tile = overlay_transform(overlay_tile)
                        _paste_tile(surface.image, overlay_tile, px, py)
                        overlay_loaded_tiles += 1
                    if use_first_overlay:
                        first_overlay = None

                    processed_tiles += 1
                    _update_progress(
                        progress_bar=progress_bar,
                        progress_callback=progress_callback,
                        processed_tiles=processed_tiles,
                        total_tiles=total_tiles,
                    )
        finally:
            if progress_bar is not None:
                progress_bar.close()

        output = Path(output_path)
        _save_output_image(surface.image, output, quality)
        preview = _create_preview_from_output(output, preview_width, preview_quality)

    return SavedCompositeRenderResult(
        output_path=output,
        preview_path=preview,
        base_loaded_tiles=base_loaded_tiles,
        overlay_loaded_tiles=overlay_loaded_tiles,
        total_tiles=total_tiles,
        tile_width=tile_width,
        tile_height=tile_height,
        used_low_memory=use_low_memory,
    )


def build_map(
    fetch_tile: FetchTileFn,
    start_x: int,
    start_y: int,
    max_search: int = 50,
    show_progress: bool = True,
    background: tuple[int, int, int] = (255, 255, 255),
) -> BuildResult:
    bounds = find_bounds(fetch_tile=fetch_tile, start_x=start_x, start_y=start_y, max_search=max_search)
    mosaic = stitch_tiles(fetch_tile=fetch_tile, bounds=bounds, show_progress=show_progress, background=background)
    return BuildResult(bounds=bounds, mosaic=mosaic)


def save_with_preview(
    image: Image.Image,
    output_path: str,
    preview_width: int = 2000,
    quality: int = 95,
    preview_quality: int = 85,
) -> str:
    output = Path(output_path)
    _save_output_image(image, output, quality)
    preview_path = _create_preview_from_output(output, preview_width, preview_quality)
    return str(preview_path)
