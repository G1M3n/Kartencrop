from __future__ import annotations

from pathlib import Path
import re
from typing import Optional

from PIL import Image

from .tiles import FetchTileFn, memoize_fetch_tile


def default_tile_cache_dir() -> Path:
    return Path.cwd() / "outputs" / "cache" / "tiles"


def _safe_namespace(namespace: str) -> str:
    parts = [re.sub(r"[^A-Za-z0-9._-]+", "_", part.strip()) for part in namespace.split("/")]
    return "/".join(part for part in parts if part)


def disk_cache_fetch_tile(
    fetch_tile: FetchTileFn,
    *,
    namespace: str,
    cache_dir: Path | str | None = None,
) -> FetchTileFn:
    base_dir = Path(cache_dir) if cache_dir is not None else default_tile_cache_dir()
    namespace_dir = base_dir / _safe_namespace(namespace)
    namespace_dir.mkdir(parents=True, exist_ok=True)

    def cached_fetch(x: int, y: int) -> Optional[Image.Image]:
        stem = namespace_dir / f"{int(x)}_{int(y)}"
        image_path = stem.with_suffix(".png")
        none_path = stem.with_suffix(".none")

        if image_path.exists():
            with Image.open(image_path) as cached_image:
                return cached_image.copy()
        if none_path.exists():
            return None

        image = fetch_tile(x, y)
        if image is None:
            none_path.touch(exist_ok=True)
            return None

        tmp_path = stem.with_suffix(".tmp.png")
        image.save(tmp_path, format="PNG")
        tmp_path.replace(image_path)
        return image.copy()

    return cached_fetch


def cached_tile_fetch(
    fetch_tile: FetchTileFn,
    *,
    namespace: str,
    cache_dir: Path | str | None = None,
) -> FetchTileFn:
    return memoize_fetch_tile(
        disk_cache_fetch_tile(
            fetch_tile,
            namespace=namespace,
            cache_dir=cache_dir,
        )
    )
