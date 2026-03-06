from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit.components.v1 as components


_COMPONENT_PATH = Path(__file__).resolve().parent / "leaflet_picker_component"
_leaflet_picker = components.declare_component("leaflet_picker", path=str(_COMPONENT_PATH))


def render_leaflet_picker(
    *,
    center_lat: float,
    center_lon: float,
    zoom: int,
    current_bbox: dict[str, float] | None,
    reset_token: int,
    key: str,
    height: int = 460,
) -> dict[str, Any] | None:
    default_value = {"point": None, "bounds": None, "selection_type": "none", "event_id": 0}
    return _leaflet_picker(
        center={"lat": float(center_lat), "lon": float(center_lon)},
        zoom=int(zoom),
        current_bbox=current_bbox,
        reset_token=int(reset_token),
        height=int(height),
        key=key,
        default=default_value,
    )
