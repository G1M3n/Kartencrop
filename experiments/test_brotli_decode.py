from __future__ import annotations

import json

from kartencrop.openaip import fetch_vector_tile, openaip_session


if __name__ == "__main__":
    try:
        import brotli
    except ImportError as exc:
        raise SystemExit("install brotli to run this script") from exc

    session = openaip_session()
    result = fetch_vector_tile(8, 134, 84, session=session)
    print(f"status={result.status_code} bytes={len(result.content)}")

    try:
        decompressed = brotli.decompress(result.content)
    except brotli.error as exc:
        print(f"brotli decompress failed: {exc}")
        raise SystemExit(0)

    print(decompressed[:300].decode("utf-8", errors="replace"))
    try:
        print(json.dumps(json.loads(decompressed), indent=2))
    except json.JSONDecodeError:
        print("decompressed payload is not json")
