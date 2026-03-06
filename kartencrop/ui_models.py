from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from .swissgeo import SwissBoundingBox
from .tiles import Bounds


AreaStrategy: TypeAlias = Literal["bounds", "component"]
OfmRenderMode: TypeAlias = Literal["single", "composite"]
OfmChartType: TypeAlias = Literal["aero", "base"]


@dataclass(slots=True)
class BaseUIConfig:
    source: str
    summary: list[str]


@dataclass(slots=True)
class OfmUIConfig(BaseUIConfig):
    zoom: int
    cycle: str
    render_mode: OfmRenderMode
    chart_type: OfmChartType
    start_x: int
    start_y: int
    coverage_search: int
    radius: int
    area_strategy: AreaStrategy
    use_detected_range: bool
    bounds: Bounds | None = None


@dataclass(slots=True)
class GeoPfUIConfig(BaseUIConfig):
    tilematrix: str
    start_x: int
    start_y: int
    coverage_search: int
    radius: int
    area_strategy: AreaStrategy
    use_detected_range: bool
    bounds: Bounds | None = None


@dataclass(slots=True)
class SwissUIConfig(BaseUIConfig):
    layers: str
    bbox: SwissBoundingBox | None
    output_width: int
    output_height: int
    image_format: str
    transparent: bool
    time: str | None
    styles: str
    identify_closures: bool
    identify_tolerance: int


@dataclass(slots=True)
class OpenAipUIConfig(BaseUIConfig):
    api_key: str | None
    layer: str
    zoom: int
    bounds: Bounds
    basemap: str
    overlay_alpha: int
    white_threshold: int
    render_vector_debug: bool
    enabled_layers: list[str] = field(default_factory=list)


UIConfig: TypeAlias = OfmUIConfig | GeoPfUIConfig | SwissUIConfig | OpenAipUIConfig
