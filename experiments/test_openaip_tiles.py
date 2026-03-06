from __future__ import annotations

from pathlib import Path

from kartencrop.openaip import fetch_vector_tile, openaip_session


def save_tile(z: int, x: int, y: int) -> None:
    session = openaip_session()
    result = fetch_vector_tile(z=z, x=x, y=y, session=session)
    print(f"status={result.status_code} type={result.content_type} size={len(result.content)}")

    if not result.ok:
        return

    path = Path(f"openaip_z{z}_x{x}_y{y}.pbf")
    path.write_bytes(result.content)
    print(f"saved: {path}")


if __name__ == "__main__":
    save_tile(12, 2158, 1453)
