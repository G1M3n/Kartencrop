from __future__ import annotations

from io import BytesIO
import os

from PIL import Image

from kartencrop.openaip import probe_urls


if __name__ == "__main__":
    z, x, y = 12, 2158, 1453
    urls = [
        f"https://api.tiles.openaip.net/api/data/openaip/{z}/{x}/{y}.pbf",
        f"https://api.tiles.openaip.net/api/data/basemap/{z}/{x}/{y}.png",
    ]

    mapbox_token = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()
    if mapbox_token:
        urls.append(
            f"https://api.mapbox.com/v4/mapbox.satellite/{z}/{x}/{y}.jpg?access_token={mapbox_token}"
        )
    else:
        print("MAPBOX_ACCESS_TOKEN nicht gesetzt; Mapbox-Test wird uebersprungen.")

    for result in probe_urls(urls):
        print(f"{result.status_code} {result.content_type} {len(result.content)} {result.url}")
        if result.ok and "image" in result.content_type.lower():
            img = Image.open(BytesIO(result.content))
            out = f"openaip_probe_{img.width}x{img.height}.png"
            img.save(out)
            print(f"saved: {out}")
