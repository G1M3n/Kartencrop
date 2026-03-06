from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

import requests
from PIL import Image

from .providers import _decode_image, _is_image_response


SWISS_WMS_ENDPOINT = "https://wms.geo.admin.ch/"
SWISS_IDENTIFY_ENDPOINT = "https://api3.geo.admin.ch/rest/services/api/MapServer/identify"
SWISS_CLOSURES_LAYER = "ch.astra.wanderland-sperrungen_umleitungen"

SWISS_WMS_LAYER_PRESETS: dict[str, str] = {
    "wanderkarte": "ch.swisstopo.pixelkarte-farbe,ch.swisstopo.swisstlm3d-wanderwege",
    "wanderkarte-sperrungen": f"ch.swisstopo.pixelkarte-farbe,ch.swisstopo.swisstlm3d-wanderwege,{SWISS_CLOSURES_LAYER}",
    "pixelkarte-farbe": "ch.swisstopo.pixelkarte-farbe",
    "wanderwege": "ch.swisstopo.swisstlm3d-wanderwege",
    "sperrungen": SWISS_CLOSURES_LAYER,
    "zeitreihe": "ch.swisstopo.zeitreihen",
}


@dataclass(frozen=True)
class SwissBoundingBox:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width_m(self) -> float:
        return self.max_x - self.min_x

    @property
    def height_m(self) -> float:
        return self.max_y - self.min_y

    @property
    def center_x(self) -> float:
        return (self.min_x + self.max_x) / 2.0

    @property
    def center_y(self) -> float:
        return (self.min_y + self.max_y) / 2.0

    def as_wms_bbox(self) -> str:
        return f"{self.min_x},{self.min_y},{self.max_x},{self.max_y}"


def wgs84_to_lv95(lat: float, lon: float) -> tuple[float, float]:
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise ValueError("lat/lon must be valid WGS84 degree values")

    lat_sec = lat * 3600.0
    lon_sec = lon * 3600.0
    lat_aux = (lat_sec - 169028.66) / 10000.0
    lon_aux = (lon_sec - 26782.5) / 10000.0

    east = (
        2600072.37
        + 211455.93 * lon_aux
        - 10938.51 * lon_aux * lat_aux
        - 0.36 * lon_aux * (lat_aux ** 2)
        - 44.54 * (lon_aux ** 3)
    )
    north = (
        1200147.07
        + 308807.95 * lat_aux
        + 3745.25 * (lon_aux ** 2)
        + 76.63 * (lat_aux ** 2)
        - 194.56 * (lon_aux ** 2) * lat_aux
        + 119.79 * (lat_aux ** 3)
    )
    return east, north


def bbox_from_wgs84_center(lat: float, lon: float, width_m: float, height_m: float) -> SwissBoundingBox:
    center_x, center_y = wgs84_to_lv95(lat, lon)
    return bbox_from_center(center_x=center_x, center_y=center_y, width_m=width_m, height_m=height_m)


def bbox_from_wgs84_bounds(lat_min: float, lon_min: float, lat_max: float, lon_max: float) -> SwissBoundingBox:
    south_west_x, south_west_y = wgs84_to_lv95(lat_min, lon_min)
    north_east_x, north_east_y = wgs84_to_lv95(lat_max, lon_max)
    min_x = min(south_west_x, north_east_x)
    max_x = max(south_west_x, north_east_x)
    min_y = min(south_west_y, north_east_y)
    max_y = max(south_west_y, north_east_y)
    if max_x <= min_x or max_y <= min_y:
        raise ValueError("wgs84 bbox max values must be greater than min values")
    return SwissBoundingBox(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y)


def bbox_from_center(center_x: float, center_y: float, width_m: float, height_m: float) -> SwissBoundingBox:
    if width_m <= 0 or height_m <= 0:
        raise ValueError("width_m and height_m must be greater than 0")

    half_width = width_m / 2.0
    half_height = height_m / 2.0
    return SwissBoundingBox(
        min_x=center_x - half_width,
        min_y=center_y - half_height,
        max_x=center_x + half_width,
        max_y=center_y + half_height,
    )


def parse_bbox(value: str) -> SwissBoundingBox:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must be formatted as min_x,min_y,max_x,max_y")

    min_x, min_y, max_x, max_y = (float(part) for part in parts)
    if max_x <= min_x or max_y <= min_y:
        raise ValueError("bbox max values must be greater than min values")
    return SwissBoundingBox(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y)


def scaled_dimensions(width: int, height: int, max_width: int = 1400) -> tuple[int, int]:
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be greater than 0")
    if width <= max_width:
        return width, height

    scale = max_width / width
    return max_width, max(1, int(height * scale))


def dimensions_from_bbox_long_edge(bbox: SwissBoundingBox, long_edge_px: int) -> tuple[int, int]:
    if long_edge_px <= 0:
        raise ValueError("long_edge_px must be greater than 0")
    if bbox.width_m <= 0 or bbox.height_m <= 0:
        raise ValueError("bbox dimensions must be greater than 0")

    aspect_ratio = bbox.width_m / bbox.height_m
    if aspect_ratio >= 1.0:
        width = int(long_edge_px)
        height = max(1, round(width / aspect_ratio))
    else:
        height = int(long_edge_px)
        width = max(1, round(height * aspect_ratio))
    return width, height


def _normalize_layers(layers: str | Iterable[str]) -> str:
    raw_layers: list[str] = []
    if isinstance(layers, str):
        raw_layers = [layer.strip() for layer in layers.split(",")]
    else:
        for layer in layers:
            raw_layers.extend(item.strip() for item in layer.split(","))

    deduped: list[str] = []
    for layer in raw_layers:
        if layer and layer not in deduped:
            deduped.append(layer)
    return ",".join(deduped)


def merge_layers(*layer_groups: str | Iterable[str]) -> str:
    merged: list[str] = []
    for group in layer_groups:
        if isinstance(group, str):
            merged.extend(part.strip() for part in group.split(","))
        else:
            for layer in group:
                merged.extend(part.strip() for part in layer.split(","))
    return _normalize_layers(merged)


def remove_layer(layers: str | Iterable[str], layer_to_remove: str) -> str:
    normalized = _normalize_layers(layers)
    return _normalize_layers([layer for layer in normalized.split(",") if layer != layer_to_remove])


@dataclass(frozen=True)
class SwissWmsRequest:
    layers: str | Iterable[str]
    bbox: SwissBoundingBox
    width: int
    height: int
    crs: str = "EPSG:2056"
    image_format: str = "image/png"
    transparent: bool = True
    time: str | None = None
    styles: str = ""

    def layer_string(self) -> str:
        return _normalize_layers(self.layers)

    def effective_transparent(self) -> bool:
        return self.transparent and self.image_format.lower() == "image/png"

    def params(self) -> dict[str, str]:
        params = {
            "SERVICE": "WMS",
            "REQUEST": "GetMap",
            "VERSION": "1.3.0",
            "LAYERS": self.layer_string(),
            "CRS": self.crs,
            "BBOX": self.bbox.as_wms_bbox(),
            "WIDTH": str(int(self.width)),
            "HEIGHT": str(int(self.height)),
            "FORMAT": self.image_format,
            "STYLES": self.styles,
            "TRANSPARENT": "TRUE" if self.effective_transparent() else "FALSE",
        }
        if self.time:
            params["TIME"] = self.time
        return params


@dataclass(frozen=True)
class SwissIdentifyRequest:
    map_extent: SwissBoundingBox
    geometry_x: float
    geometry_y: float
    image_width: int
    image_height: int
    dpi: int = 96
    sr: int = 2056
    tolerance: int = 0
    geometry_type: str = "esriGeometryPoint"
    layers: str = f'all:{SWISS_CLOSURES_LAYER}'

    def params(self) -> dict[str, str]:
        return {
            "layers": self.layers,
            "geometry": f"{self.geometry_x},{self.geometry_y}",
            "geometryType": self.geometry_type,
            "tolerance": str(int(self.tolerance)),
            "mapExtent": self.map_extent.as_wms_bbox(),
            "imageDisplay": f"{int(self.image_width)},{int(self.image_height)},{int(self.dpi)}",
            "sr": str(int(self.sr)),
        }


@dataclass
class SwissGeoAdminWmsProvider:
    timeout: float = 20.0
    endpoint: str = SWISS_WMS_ENDPOINT
    session: requests.Session = field(default_factory=requests.Session)

    def __post_init__(self) -> None:
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Referer": "https://map.geo.admin.ch/",
            }
        )

    def fetch_map(
        self,
        *,
        layers: str | Iterable[str],
        bbox: SwissBoundingBox,
        width: int,
        height: int,
        crs: str = "EPSG:2056",
        image_format: str = "image/png",
        transparent: bool = True,
        time: Optional[str] = None,
        styles: str = "",
    ) -> Optional[Image.Image]:
        request = SwissWmsRequest(
            layers=layers,
            bbox=bbox,
            width=width,
            height=height,
            crs=crs,
            image_format=image_format,
            transparent=transparent,
            time=time,
            styles=styles,
        )

        try:
            resp = self.session.get(self.endpoint, params=request.params(), timeout=self.timeout)
        except requests.RequestException:
            return None

        if not _is_image_response(resp):
            return None

        return _decode_image(resp.content, preserve_alpha=request.effective_transparent())


@dataclass
class SwissGeoAdminFeatureProvider:
    timeout: float = 20.0
    identify_endpoint: str = SWISS_IDENTIFY_ENDPOINT
    session: requests.Session = field(default_factory=requests.Session)

    def __post_init__(self) -> None:
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Referer": "https://map.geo.admin.ch/",
                "Accept": "application/json",
            }
        )

    def identify_features(
        self,
        *,
        bbox: SwissBoundingBox,
        geometry_x: float,
        geometry_y: float,
        image_width: int,
        image_height: int,
        tolerance: int = 0,
        layers: str = f'all:{SWISS_CLOSURES_LAYER}',
        sr: int = 2056,
        dpi: int = 96,
    ) -> list[dict[str, Any]] | None:
        request = SwissIdentifyRequest(
            map_extent=bbox,
            geometry_x=geometry_x,
            geometry_y=geometry_y,
            image_width=image_width,
            image_height=image_height,
            tolerance=tolerance,
            layers=layers,
            sr=sr,
            dpi=dpi,
        )

        try:
            resp = self.session.get(self.identify_endpoint, params=request.params(), timeout=self.timeout)
        except requests.RequestException:
            return None

        content_type = resp.headers.get("Content-Type", "").lower()
        if resp.status_code != 200 or "json" not in content_type:
            return None

        try:
            payload = resp.json()
        except ValueError:
            return None

        results = payload.get("results")
        if not isinstance(results, list):
            return []
        return results
