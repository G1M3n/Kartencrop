from __future__ import annotations

from pathlib import Path

from kartencrop.openaip import fetch_vector_tile, openaip_session


def load_grid(z: int, start_x: int, start_y: int, width: int = 3, height: int = 3) -> None:
    session = openaip_session()
    loaded = 0
    total = width * height

    for dy in range(height):
        for dx in range(width):
            x = start_x + dx
            y = start_y + dy
            result = fetch_vector_tile(z=z, x=x, y=y, session=session)
            if not result.ok:
                print(f"missing z{z}/{x}/{y}: {result.status_code}")
                continue
            path = Path(f"openaip_tile_z{z}_x{x}_y{y}.pbf")
            path.write_bytes(result.content)
            loaded += 1
            print(f"saved: {path}")

    print(f"loaded {loaded}/{total}")


if __name__ == "__main__":
    load_grid(z=5, start_x=15, start_y=11)
