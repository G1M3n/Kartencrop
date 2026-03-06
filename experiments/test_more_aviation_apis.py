from __future__ import annotations

from io import BytesIO

from PIL import Image

from kartencrop.openaip import probe_urls


if __name__ == "__main__":
    urls = [
        "https://skyvector.com/tiles/301/8/134/84",
        "https://tiles.skyvector.com/vfr/8/134/84.jpg",
        "https://maps.wikimedia.org/osm-intl/8/134/84.png",
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/8/84/134",
    ]

    for result in probe_urls(urls):
        print(f"{result.status_code:3d} {result.content_type:30s} {len(result.content):8d} {result.url}")
        if not (result.ok and "image" in result.content_type.lower()):
            continue
        img = Image.open(BytesIO(result.content))
        out = f"test_source_{img.width}x{img.height}_{abs(hash(result.url)) % 10000}.png"
        img.save(out)
        print(f"saved: {out}")
