from kartencrop.cli import _ofm_bounds_from_bbox, build_parser
from kartencrop.geo import bbox_to_tile_bounds
from kartencrop.tiles import Bounds
from kartencrop.ui_actions import _geopf_target_bounds, _ofm_target_bounds
from kartencrop.ui_models import GeoPfUIConfig, OfmUIConfig


def test_ofm_bounds_from_bbox_matches_geo_helper() -> None:
    tile_bounds = bbox_to_tile_bounds(35.0, -10.0, 62.0, 25.0, 8)
    bounds = _ofm_bounds_from_bbox(zoom=8, lat_min=35.0, lon_min=-10.0, lat_max=62.0, lon_max=25.0)

    assert bounds == Bounds(
        min_x=tile_bounds.min_x,
        max_x=tile_bounds.max_x,
        min_y=tile_bounds.min_y,
        max_y=tile_bounds.max_y,
    )


def test_ofm_target_bounds_uses_explicit_bounds_without_anchor_search() -> None:
    calls: list[tuple[int, int]] = []
    explicit_bounds = Bounds(min_x=1, max_x=3, min_y=4, max_y=6)

    def fetch_tile(x: int, y: int):
        calls.append((x, y))
        return None

    bounds, detected, corrected = _ofm_target_bounds(
        OfmUIConfig(
            source="ofm",
            zoom=8,
            cycle="latest",
            render_mode="single",
            chart_type="aero",
            start_x=999,
            start_y=999,
            coverage_search=0,
            radius=0,
            area_strategy="bounds",
            use_detected_range=False,
            bounds=explicit_bounds,
            summary=[],
        ),
        fetch_tile,
    )

    assert bounds == explicit_bounds
    assert detected is None
    assert corrected is None
    assert calls == []


def test_cli_accepts_ofm_bbox_commands() -> None:
    parser = build_parser()

    bbox_args = parser.parse_args(
        [
            "ofm-bbox",
            "--zoom",
            "8",
            "--lat-min",
            "35",
            "--lon-min",
            "-10",
            "--lat-max",
            "62",
            "--lon-max",
            "25",
        ]
    )
    composite_args = parser.parse_args(
        [
            "ofm-composite-bbox",
            "--zoom",
            "8",
            "--lat-min",
            "35",
            "--lon-min",
            "-10",
            "--lat-max",
            "62",
            "--lon-max",
            "25",
        ]
    )

    assert bbox_args.command == "ofm-bbox"
    assert composite_args.command == "ofm-composite-bbox"


def test_geopf_target_bounds_uses_explicit_bounds_without_anchor_search() -> None:
    calls: list[tuple[int, int]] = []
    explicit_bounds = Bounds(min_x=30, max_x=33, min_y=21, max_y=24)

    def fetch_tile(x: int, y: int):
        calls.append((x, y))
        return None

    bounds, detected, corrected = _geopf_target_bounds(
        GeoPfUIConfig(
            source="geopf",
            tilematrix="11",
            start_x=999,
            start_y=999,
            coverage_search=0,
            radius=0,
            area_strategy="bounds",
            use_detected_range=False,
            bounds=explicit_bounds,
            summary=[],
        ),
        fetch_tile,
    )

    assert bounds == explicit_bounds
    assert detected is None
    assert corrected is None
    assert calls == []
