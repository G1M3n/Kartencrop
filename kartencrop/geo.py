from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class TileCoord:
    x: int
    y: int
    z: int


@dataclass(frozen=True)
class TileBounds:
    min_x: int
    max_x: int
    min_y: int
    max_y: int
    z: int

    @property
    def width(self) -> int:
        return self.max_x - self.min_x + 1

    @property
    def height(self) -> int:
        return self.max_y - self.min_y + 1

    @property
    def center_x(self) -> int:
        return (self.min_x + self.max_x) // 2

    @property
    def center_y(self) -> int:
        return (self.min_y + self.max_y) // 2


@dataclass(frozen=True)
class GeoBounds:
    lat_min: float
    lon_min: float
    lat_max: float
    lon_max: float

    @property
    def center_lat(self) -> float:
        return (self.lat_min + self.lat_max) / 2.0

    @property
    def center_lon(self) -> float:
        return (self.lon_min + self.lon_max) / 2.0


def latlon_to_tile(lat: float, lon: float, z: int) -> TileCoord:
    lat_clamped = max(min(lat, 85.05112878), -85.05112878)
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat_clamped)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return TileCoord(x=x, y=y, z=z)


def bbox_to_tile_bounds(lat_min: float, lon_min: float, lat_max: float, lon_max: float, z: int) -> TileBounds:
    north = latlon_to_tile(lat_max, lon_min, z)
    south = latlon_to_tile(lat_min, lon_max, z)
    min_x = min(north.x, south.x)
    max_x = max(north.x, south.x)
    min_y = min(north.y, south.y)
    max_y = max(north.y, south.y)
    return TileBounds(min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y, z=z)


def tile_corner_to_latlon(x: int, y: int, z: int) -> tuple[float, float]:
    n = 2 ** z
    lon = float(x) / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1.0 - (2.0 * float(y) / n))))
    lat = math.degrees(lat_rad)
    return lat, lon


def tile_bounds_to_geo_bounds(bounds: TileBounds) -> GeoBounds:
    north_lat, west_lon = tile_corner_to_latlon(bounds.min_x, bounds.min_y, bounds.z)
    south_lat, east_lon = tile_corner_to_latlon(bounds.max_x + 1, bounds.max_y + 1, bounds.z)
    return GeoBounds(
        lat_min=south_lat,
        lon_min=west_lon,
        lat_max=north_lat,
        lon_max=east_lon,
    )
