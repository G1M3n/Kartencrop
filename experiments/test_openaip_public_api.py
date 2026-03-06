from __future__ import annotations

from kartencrop.openaip import probe_urls


if __name__ == "__main__":
    urls = [
        "https://api.tiles.openaip.net/styles/openaip/8/134/84.png",
        "https://api.tiles.openaip.net/styles/openaip/8/134/84.jpg",
        "https://tiles.openaip.net/openaip/8/134/84.png",
        "https://cdn.openaip.net/tiles/openaip/8/134/84.png",
    ]

    results = probe_urls(urls)
    for result in results:
        print(f"{result.status_code:3d} {result.content_type:30s} {len(result.content):8d} {result.url}")
