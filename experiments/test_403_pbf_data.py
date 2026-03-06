from __future__ import annotations

import gzip

from kartencrop.openaip import fetch_vector_tile, openaip_session


def maybe_decode_pbf(payload: bytes) -> None:
    try:
        import mapbox_vector_tile
    except ImportError:
        print("mapbox-vector-tile not installed; skipping decode")
        return

    decoded = mapbox_vector_tile.decode(payload)
    print(f"decoded layers: {list(decoded.keys())}")


if __name__ == "__main__":
    session = openaip_session()
    for z, x, y in [(8, 134, 84), (8, 136, 89), (9, 270, 170)]:
        result = fetch_vector_tile(z, x, y, session=session)
        print(f"z{z}/{x}/{y}: status={result.status_code} bytes={len(result.content)}")

        payload = result.content
        if payload[:2] == b"\x1f\x8b":
            payload = gzip.decompress(payload)
            print(f"gzip -> {len(payload)} bytes")

        maybe_decode_pbf(payload)
