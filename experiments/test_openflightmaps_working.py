from __future__ import annotations

from kartencrop.providers import OpenFlightMapsProvider


def test_tiles(cycle: str = "latest") -> None:
    provider = OpenFlightMapsProvider(zoom=8, cycle=cycle)
    test_cases = [
        (144, 72, "center"),
        (143, 72, "left"),
        (145, 72, "right"),
        (144, 71, "top"),
        (144, 73, "bottom"),
    ]

    loaded = 0
    for x, y, label in test_cases:
        img = provider.fetch_tile(x, y)
        if img is None:
            print(f"{label}: missing ({x},{y})")
            continue
        loaded += 1
        out = f"openflightmaps_z8_x{x}_y{y}.png"
        img.save(out)
        print(f"{label}: ok ({x},{y}) -> {out}")

    print(f"loaded {loaded}/{len(test_cases)}")


if __name__ == "__main__":
    test_tiles()
