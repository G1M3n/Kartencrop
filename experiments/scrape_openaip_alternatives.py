from __future__ import annotations

from kartencrop.http import create_session, request_bytes
from kartencrop.openaip import fetch_vector_tile, openaip_session, probe_urls


def method_session_tile() -> bool:
    session = openaip_session()
    result = fetch_vector_tile(5, 16, 12, session=session)
    print(f"session tile: status={result.status_code} size={len(result.content)}")
    if not result.ok:
        return False
    with open("openaip_method_session_tile.pbf", "wb") as f:
        f.write(result.content)
    return True


def method_alternative_endpoints() -> bool:
    urls = [
        "https://api.tiles.openaip.net/api/data/openaip/5/16/12.pbf",
        "https://tiles.openaip.net/api/data/openaip/5/16/12.pbf",
        "https://cache.openaip.net/api/data/openaip/5/16/12.pbf",
    ]
    ok = False
    for result in probe_urls(urls):
        print(f"probe: {result.status_code} {result.url}")
        ok = ok or result.ok
    return ok


def method_download_pages() -> bool:
    urls = [
        "https://www.openaip.net/download",
        "https://download.openaip.net",
        "https://data.openaip.net",
    ]
    session = create_session()
    ok = False
    for url in urls:
        result = request_bytes(url, session=session)
        print(f"page: {result.status_code} {url}")
        if result.ok:
            ok = True
            with open(f"openaip_page_{abs(hash(url)) % 10000}.html", "wb") as f:
                f.write(result.content)
    return ok


if __name__ == "__main__":
    results = {
        "session": method_session_tile(),
        "alt_endpoints": method_alternative_endpoints(),
        "download_pages": method_download_pages(),
    }
    print(results)
