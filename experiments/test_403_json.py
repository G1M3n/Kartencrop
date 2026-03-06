from __future__ import annotations

import json

from kartencrop.openaip import fetch_vector_tile, openaip_session


if __name__ == "__main__":
    session = openaip_session()
    result = fetch_vector_tile(8, 134, 84, session=session)

    print(f"status: {result.status_code}")
    print(f"content-type: {result.content_type}")
    print(f"bytes: {len(result.content)}")
    print(f"magic: {result.content[:4].hex()}")

    text = result.content.decode("utf-8", errors="replace")
    print(text[:400])

    try:
        parsed = json.loads(text)
        print(json.dumps(parsed, indent=2))
    except json.JSONDecodeError:
        print("response is not json")
