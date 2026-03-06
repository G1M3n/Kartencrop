from __future__ import annotations

from kartencrop.cli import main


if __name__ == "__main__":
    raise SystemExit(
        main(
            [
                "ofm-full",
                "--zoom",
                "8",
                "--start-x",
                "144",
                "--start-y",
                "72",
                "--max-search",
                "50",
                "--output",
                "openflightmaps_finland_z8_full.jpg",
                "--cycle",
                "latest",
            ]
        )
    )
