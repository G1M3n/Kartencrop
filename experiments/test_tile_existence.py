from __future__ import annotations

from dataclasses import dataclass

from kartencrop.providers import GeoPfProvider


@dataclass(frozen=True)
class TileCheck:
    col: int
    row: int
    exists: bool


def check_tile(tilecol: int, tilerow: int, tilematrix: str = "11") -> TileCheck:
    provider = GeoPfProvider(tilematrix=tilematrix)
    img = provider.fetch_tile(tilecol, tilerow)
    return TileCheck(col=tilecol, row=tilerow, exists=img is not None)


if __name__ == "__main__":
    test_cases = [(0, 0), (1025, 721), (1026, 721), (9999, 9999)]
    for col, row in test_cases:
        result = check_tile(col, row)
        status = "exists" if result.exists else "missing"
        print(f"col={result.col} row={result.row} -> {status}")
