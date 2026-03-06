from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Iterable, Optional
from urllib.parse import urlencode

import requests

from .http import HttpResult, create_session, request_bytes, warmup_session


OPENAIP_MAP_URL = "https://www.openaip.net/map"
OPENAIP_VECTOR_TEMPLATE = "https://api.tiles.openaip.net/api/data/{layer}/{z}/{x}/{y}.pbf"
OPENAIP_RASTER_TEMPLATE = "https://api.tiles.openaip.net/api/data/{layer}/{z}/{x}/{y}.png"
OPENAIP_STYLE_TEMPLATE = "https://api.tiles.openaip.net/api/styles/{style}.json"


@dataclass(frozen=True)
class TileRequest:
    layer: str
    z: int
    x: int
    y: int

    def vector_url(self, api_key: str | None = None) -> str:
        base = OPENAIP_VECTOR_TEMPLATE.format(layer=self.layer, z=self.z, x=self.x, y=self.y)
        if not api_key:
            return base
        return f"{base}?{urlencode({'apiKey': api_key})}"

    def raster_url(self, api_key: str | None = None) -> str:
        base = OPENAIP_RASTER_TEMPLATE.format(layer=self.layer, z=self.z, x=self.x, y=self.y)
        if not api_key:
            return base
        return f"{base}?{urlencode({'apiKey': api_key})}"


def openaip_session() -> requests.Session:
    session = create_session()
    warmup_session(session, OPENAIP_MAP_URL)
    return session


def fetch_vector_tile(
    z: int,
    x: int,
    y: int,
    layer: str = "openaip",
    session: Optional[requests.Session] = None,
    api_key: str | None = None,
    bearer_token: str | None = None,
    timeout: float = 15.0,
) -> HttpResult:
    req_session = session or openaip_session()
    key = api_key or os.getenv("OPENAIP_API_KEY")
    token = bearer_token or os.getenv("OPENAIP_BEARER_TOKEN")

    headers = {
        "Accept": "*/*",
        "Origin": "https://www.openaip.net",
        "Referer": "https://www.openaip.net/map",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if key:
        headers["x-openaip-api-key"] = key

    return request_bytes(
        TileRequest(layer=layer, z=z, x=x, y=y).vector_url(api_key=key),
        session=req_session,
        headers=headers,
        timeout=timeout,
    )


def fetch_raster_tile(
    z: int,
    x: int,
    y: int,
    layer: str = "openaip",
    session: Optional[requests.Session] = None,
    api_key: str | None = None,
    bearer_token: str | None = None,
    timeout: float = 15.0,
) -> HttpResult:
    req_session = session or openaip_session()
    key = api_key or os.getenv("OPENAIP_API_KEY")
    token = bearer_token or os.getenv("OPENAIP_BEARER_TOKEN")

    headers = {
        "Accept": "*/*",
        "Origin": "https://www.openaip.net",
        "Referer": "https://www.openaip.net/map",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if key:
        headers["x-openaip-api-key"] = key

    return request_bytes(
        TileRequest(layer=layer, z=z, x=x, y=y).raster_url(api_key=key),
        session=req_session,
        headers=headers,
        timeout=timeout,
    )


def fetch_style(
    style: str,
    session: Optional[requests.Session] = None,
    timeout: float = 10.0,
) -> HttpResult:
    req_session = session or create_session()
    return request_bytes(url=OPENAIP_STYLE_TEMPLATE.format(style=style), session=req_session, timeout=timeout)


def probe_urls(
    urls: Iterable[str],
    session: Optional[requests.Session] = None,
    timeout: float = 10.0,
) -> list[HttpResult]:
    req_session = session or create_session()
    results: list[HttpResult] = []
    for url in urls:
        results.append(request_bytes(url=url, session=req_session, timeout=timeout))
    return results
