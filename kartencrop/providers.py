from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
import os
from typing import Optional

import requests
from PIL import Image

from .capabilities import (
    DEFAULT_GEOPF_SCAN_OACI_LIMITS,
    get_geopf_scan_oaci_limits,
)
from .http import get_with_retries


# Historical sample bounds kept only to derive the currently verified OFM zoom
# range. OFM coverage itself is regional and irregular across Europe.
OFM_VERIFIED_TILE_SAMPLES: dict[int, tuple[int, int, int, int]] = {
    7: (69, 74, 30, 50),
    8: (136, 149, 66, 100),
    9: (279, 300, 127, 150),
    10: (568, 599, 256, 291),
    11: (1149, 1154, 563, 582),
    12: (2299, 2310, 1130, 1151),
}
# Backward-compatible alias for existing imports and tests.
OFM_FINLAND_TILE_LIMITS = OFM_VERIFIED_TILE_SAMPLES
OFM_MIN_ZOOM = min(OFM_VERIFIED_TILE_SAMPLES)
OFM_MAX_ZOOM = max(OFM_VERIFIED_TILE_SAMPLES)

GEOPF_SCAN_OACI_LIMITS: dict[int, tuple[int, int, int, int]] = dict(DEFAULT_GEOPF_SCAN_OACI_LIMITS)
GEOPF_MIN_TILEMATRIX = min(GEOPF_SCAN_OACI_LIMITS)
GEOPF_MAX_TILEMATRIX = max(GEOPF_SCAN_OACI_LIMITS)

OPENAIP_MIN_ZOOM = 1
OPENAIP_MAX_ZOOM = 20


def _validate_int_range(name: str, value: int, min_value: int, max_value: int) -> int:
    if int(value) < min_value or int(value) > max_value:
        raise ValueError(f"{name} must be between {min_value} and {max_value}")
    return int(value)


def _is_image_response(resp: requests.Response) -> bool:
    return resp.status_code == 200 and "image" in resp.headers.get("Content-Type", "").lower()


def _decode_image(payload: bytes, preserve_alpha: bool = False) -> Optional[Image.Image]:
    image = Image.open(BytesIO(payload))

    # PNG palette images can carry transparency bytes; normalize first to avoid
    # PIL conversion warnings and preserve alpha handling.
    if image.mode == "P" and "transparency" in image.info:
        image = image.convert("RGBA")

    if image.mode in {"RGBA", "LA"}:
        # Some providers return a fully transparent placeholder tile when
        # no chart data is available.
        alpha = image.getchannel("A")
        if alpha.getbbox() is None:
            return None

        if preserve_alpha:
            return image.convert("RGBA")

        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=alpha)
        return background

    if preserve_alpha:
        return image.convert("RGBA")
    return image.convert("RGB")


@dataclass
class OpenFlightMapsProvider:
    zoom: int
    cycle: str = "latest"
    chart_type: str = "aero"
    preserve_alpha: bool = False
    timeout: float = 10.0
    session: requests.Session = field(default_factory=requests.Session)

    def __post_init__(self) -> None:
        self.zoom = _validate_int_range("OpenFlightMaps zoom", self.zoom, OFM_MIN_ZOOM, OFM_MAX_ZOOM)
        self.chart_type = self.chart_type.strip().lower()
        if self.chart_type not in {"aero", "base"}:
            raise ValueError("chart_type must be 'aero' or 'base'")
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Referer": "https://openflightmaps.org/",
            }
        )

    def fetch_tile(self, x: int, y: int) -> Optional[Image.Image]:
        extension = "jpg" if self.chart_type == "base" else "png"
        url = (
            "https://nwy-tiles-api.prod.newaydata.com/tiles/"
            f"{self.zoom}/{x}/{y}.{extension}?path={self.cycle}/{self.chart_type}/latest"
        )
        resp = get_with_retries(self.session, url, timeout=self.timeout)
        if resp is None:
            return None

        if not _is_image_response(resp):
            return None
        return _decode_image(resp.content, preserve_alpha=self.preserve_alpha)

    def cache_namespace(self) -> str:
        return f"ofm/z{self.zoom}/{self.cycle}/{self.chart_type}/alpha-{int(self.preserve_alpha)}"


@dataclass
class GeoPfProvider:
    tilematrix: str = "11"
    timeout: float = 10.0
    apikey: str = "ign_scan_ws"
    layer: str = "GEOGRAPHICALGRIDSYSTEMS.MAPS.SCAN-OACI"
    session: requests.Session = field(default_factory=requests.Session)

    def __post_init__(self) -> None:
        tilematrix_value = _validate_int_range(
            "GeoPF TileMatrix",
            int(self.tilematrix),
            GEOPF_MIN_TILEMATRIX,
            GEOPF_MAX_TILEMATRIX,
        )
        self.tilematrix = str(tilematrix_value)
        self.session.headers.update({"User-Agent": "Python-requests/WMTS-mapper"})

    def fetch_tile(self, col: int, row: int) -> Optional[Image.Image]:
        base = "https://data.geopf.fr/private/wmts"
        params = {
            "apikey": self.apikey,
            "layer": self.layer,
            "style": "normal",
            "tilematrixset": "PM",
            "Service": "WMTS",
            "Request": "GetTile",
            "Version": "1.0.0",
            "Format": "image/jpeg",
            "TileMatrix": self.tilematrix,
            "TileCol": str(col),
            "TileRow": str(row),
        }

        resp = get_with_retries(self.session, base, params=params, timeout=self.timeout)
        if resp is None:
            return None

        if not _is_image_response(resp):
            return None
        return _decode_image(resp.content)

    def cache_namespace(self) -> str:
        return f"geopf/tm-{self.tilematrix}/{self.layer}"


def geopf_scan_oaci_limits(*, refresh: bool = False, timeout: float = 10.0) -> dict[int, tuple[int, int, int, int]]:
    return get_geopf_scan_oaci_limits(refresh=refresh, timeout=timeout)


@dataclass
class OpenAipRasterProvider:
    zoom: int
    layer: str = "openaip"
    timeout: float = 15.0
    api_key: str | None = None
    bearer_token: str | None = None
    session: requests.Session = field(default_factory=requests.Session)

    def __post_init__(self) -> None:
        self.zoom = _validate_int_range("OpenAIP zoom", self.zoom, OPENAIP_MIN_ZOOM, OPENAIP_MAX_ZOOM)
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept": "*/*",
                "Origin": "https://www.openaip.net",
                "Referer": "https://www.openaip.net/map",
            }
        )
        if not self.api_key:
            self.api_key = os.getenv("OPENAIP_API_KEY")
        if not self.bearer_token:
            self.bearer_token = os.getenv("OPENAIP_BEARER_TOKEN")

    def fetch_tile(self, x: int, y: int) -> Optional[Image.Image]:
        url = f"https://api.tiles.openaip.net/api/data/{self.layer}/{self.zoom}/{x}/{y}.png"
        params = {"apiKey": self.api_key} if self.api_key else None
        headers: dict[str, str] = {}
        if self.api_key:
            headers["x-openaip-api-key"] = self.api_key
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"

        resp = get_with_retries(
            self.session,
            url,
            params=params,
            headers=headers,
            timeout=self.timeout,
        )
        if resp is None:
            return None

        if not _is_image_response(resp):
            return None
        return _decode_image(resp.content)

    def cache_namespace(self) -> str:
        return f"openaip/{self.layer}/z{self.zoom}"


@dataclass
class EsriProvider:
    zoom: int
    service: str = "World_Topo_Map"
    timeout: float = 15.0
    session: requests.Session = field(default_factory=requests.Session)

    def __post_init__(self) -> None:
        self.session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

    def fetch_tile(self, x: int, y: int) -> Optional[Image.Image]:
        # ArcGIS tile scheme uses /tile/{z}/{y}/{x}
        url = (
            "https://server.arcgisonline.com/ArcGIS/rest/services/"
            f"{self.service}/MapServer/tile/{self.zoom}/{y}/{x}"
        )
        resp = get_with_retries(self.session, url, timeout=self.timeout)
        if resp is None:
            return None

        if not _is_image_response(resp):
            return None
        return _decode_image(resp.content)

    def cache_namespace(self) -> str:
        return f"esri/{self.service}/z{self.zoom}"
