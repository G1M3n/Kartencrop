from __future__ import annotations

from kartencrop.cli import main


if __name__ == "__main__":
    raise SystemExit(
        main(
            [
                "geopf-full",
                "--tilematrix",
                "11",
                "--start-col",
                "1025",
                "--start-row",
                "721",
                "--max-search",
                "100",
                "--output",
                "france_aviation_map_full.jpg",
            ]
        )
    )
