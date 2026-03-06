from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Optional
from xml.etree import ElementTree as ET

import requests

from .http import get_with_retries


DEFAULT_GEOPF_SCAN_OACI_LIMITS: dict[int, tuple[int, int, int, int]] = {
    6: (30, 33, 21, 24),
    7: (61, 67, 42, 48),
    8: (123, 135, 85, 96),
    9: (247, 271, 170, 193),
    10: (494, 543, 340, 386),
    11: (989, 1087, 681, 772),
}

GEOPF_CAPABILITIES_CACHE_TTL_SECONDS = 24 * 60 * 60
GEOPF_CAPABILITIES_URL = "https://data.geopf.fr/private/wmts"
GEOPF_CAPABILITIES_LAYER = "GEOGRAPHICALGRIDSYSTEMS.MAPS.SCAN-OACI"
GEOPF_CAPABILITIES_TILEMATRIXSET = "PM"
GEOPF_CAPABILITIES_CACHE_PATH = Path.cwd() / "outputs" / "cache" / "capabilities" / "geopf_scan_oaci_limits.json"

WMTS_NAMESPACES = {
    "wmts": "http://www.opengis.net/wmts/1.0",
    "ows": "http://www.opengis.net/ows/1.1",
}


@dataclass(frozen=True)
class GeoPfCapabilities:
    limits: dict[int, tuple[int, int, int, int]]
    source: str
    fetched_at: float | None = None


_GEOPF_CAPABILITIES_CACHE: GeoPfCapabilities | None = None


def parse_geopf_capabilities_xml(
    xml_text: str,
    *,
    layer: str = GEOPF_CAPABILITIES_LAYER,
    tilematrixset: str = GEOPF_CAPABILITIES_TILEMATRIXSET,
) -> dict[int, tuple[int, int, int, int]]:
    root = ET.fromstring(xml_text)
    for layer_element in root.findall(".//wmts:Contents/wmts:Layer", WMTS_NAMESPACES):
        identifier = layer_element.findtext("ows:Identifier", namespaces=WMTS_NAMESPACES)
        if identifier != layer:
            continue
        for link in layer_element.findall("wmts:TileMatrixSetLink", WMTS_NAMESPACES):
            linked_set = link.findtext("wmts:TileMatrixSet", namespaces=WMTS_NAMESPACES)
            if linked_set != tilematrixset:
                continue
            limits_element = link.find("wmts:TileMatrixSetLimits", WMTS_NAMESPACES)
            if limits_element is None:
                continue
            parsed_limits: dict[int, tuple[int, int, int, int]] = {}
            for tile_matrix_limits in limits_element.findall("wmts:TileMatrixLimits", WMTS_NAMESPACES):
                tile_matrix_name = tile_matrix_limits.findtext("wmts:TileMatrix", namespaces=WMTS_NAMESPACES)
                if tile_matrix_name is None:
                    continue
                tile_matrix_level = int(tile_matrix_name.split(":")[-1])
                min_row = int(tile_matrix_limits.findtext("wmts:MinTileRow", namespaces=WMTS_NAMESPACES))
                max_row = int(tile_matrix_limits.findtext("wmts:MaxTileRow", namespaces=WMTS_NAMESPACES))
                min_col = int(tile_matrix_limits.findtext("wmts:MinTileCol", namespaces=WMTS_NAMESPACES))
                max_col = int(tile_matrix_limits.findtext("wmts:MaxTileCol", namespaces=WMTS_NAMESPACES))
                parsed_limits[tile_matrix_level] = (min_col, max_col, min_row, max_row)
            if parsed_limits:
                return dict(sorted(parsed_limits.items()))
    raise ValueError("GeoPF WMTS capabilities do not contain tile limits for the requested layer.")


def _serialize_limits(limits: dict[int, tuple[int, int, int, int]]) -> dict[str, list[int]]:
    return {str(level): [int(value) for value in bounds] for level, bounds in sorted(limits.items())}


def _deserialize_limits(data: dict[str, list[int]]) -> dict[int, tuple[int, int, int, int]]:
    return {
        int(level): (int(bounds[0]), int(bounds[1]), int(bounds[2]), int(bounds[3]))
        for level, bounds in data.items()
        if isinstance(bounds, list) and len(bounds) == 4
    }


def _load_capabilities_from_cache(*, allow_stale: bool) -> GeoPfCapabilities | None:
    if not GEOPF_CAPABILITIES_CACHE_PATH.exists():
        return None
    try:
        payload = json.loads(GEOPF_CAPABILITIES_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None

    fetched_at = payload.get("fetched_at")
    if not allow_stale and isinstance(fetched_at, (int, float)):
        if time.time() - float(fetched_at) > GEOPF_CAPABILITIES_CACHE_TTL_SECONDS:
            return None

    limits_raw = payload.get("limits")
    if not isinstance(limits_raw, dict):
        return None
    limits = _deserialize_limits(limits_raw)
    if not limits:
        return None
    return GeoPfCapabilities(limits=limits, source="cache", fetched_at=float(fetched_at) if isinstance(fetched_at, (int, float)) else None)


def _persist_capabilities_to_cache(capabilities: GeoPfCapabilities) -> None:
    GEOPF_CAPABILITIES_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": capabilities.fetched_at or time.time(),
        "limits": _serialize_limits(capabilities.limits),
    }
    temp_path = GEOPF_CAPABILITIES_CACHE_PATH.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    temp_path.replace(GEOPF_CAPABILITIES_CACHE_PATH)


def load_geopf_capabilities(
    *,
    refresh: bool = False,
    timeout: float = 10.0,
    session: requests.Session | None = None,
) -> GeoPfCapabilities:
    global _GEOPF_CAPABILITIES_CACHE

    if _GEOPF_CAPABILITIES_CACHE is not None and not refresh:
        return _GEOPF_CAPABILITIES_CACHE

    if not refresh:
        cached = _load_capabilities_from_cache(allow_stale=False)
        if cached is not None:
            _GEOPF_CAPABILITIES_CACHE = cached
            return cached

    client = session or requests.Session()
    response = get_with_retries(
        client,
        GEOPF_CAPABILITIES_URL,
        params={
            "SERVICE": "WMTS",
            "VERSION": "1.0.0",
            "REQUEST": "GetCapabilities",
            "apikey": "ign_scan_ws",
        },
        timeout=timeout,
    )
    if response is not None and response.status_code == 200:
        try:
            limits = parse_geopf_capabilities_xml(response.text)
        except ValueError:
            limits = {}
        if limits:
            capabilities = GeoPfCapabilities(limits=limits, source="live", fetched_at=time.time())
            _persist_capabilities_to_cache(capabilities)
            _GEOPF_CAPABILITIES_CACHE = capabilities
            return capabilities

    cached = _load_capabilities_from_cache(allow_stale=True)
    if cached is not None:
        _GEOPF_CAPABILITIES_CACHE = cached
        return cached

    fallback = GeoPfCapabilities(limits=dict(DEFAULT_GEOPF_SCAN_OACI_LIMITS), source="fallback", fetched_at=None)
    _GEOPF_CAPABILITIES_CACHE = fallback
    return fallback


def get_geopf_scan_oaci_limits(*, refresh: bool = False, timeout: float = 10.0) -> dict[int, tuple[int, int, int, int]]:
    return load_geopf_capabilities(refresh=refresh, timeout=timeout).limits


def get_geopf_tilematrix_range(*, refresh: bool = False, timeout: float = 10.0) -> tuple[int, int]:
    limits = get_geopf_scan_oaci_limits(refresh=refresh, timeout=timeout)
    return min(limits), max(limits)


def geopf_capabilities_source(*, refresh: bool = False, timeout: float = 10.0) -> str:
    return load_geopf_capabilities(refresh=refresh, timeout=timeout).source
