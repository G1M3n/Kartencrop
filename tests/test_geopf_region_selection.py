from kartencrop.cli import _geopf_bounds_from_bbox, _geopf_bounds_from_center, build_parser
from kartencrop.providers import GEOPF_SCAN_OACI_LIMITS


def test_geopf_bounds_from_center_are_clipped_to_known_range() -> None:
    tile, bounds = _geopf_bounds_from_center(tilematrix=11, lat=46.227638, lon=2.213749, radius=50)

    assert bounds is not None
    min_col, max_col, min_row, max_row = GEOPF_SCAN_OACI_LIMITS[11]
    assert bounds.min_x >= min_col
    assert bounds.max_x <= max_col
    assert bounds.min_y >= min_row
    assert bounds.max_y <= max_row
    assert min_col <= tile.x <= max_col
    assert min_row <= tile.y <= max_row


def test_geopf_bounds_from_bbox_are_clipped_to_known_range() -> None:
    tile_bounds, bounds = _geopf_bounds_from_bbox(tilematrix=11, lat_min=41.0, lon_min=-10.0, lat_max=52.0, lon_max=10.0)

    assert bounds is not None
    min_col, max_col, min_row, max_row = GEOPF_SCAN_OACI_LIMITS[11]
    assert bounds.min_x >= min_col
    assert bounds.max_x <= max_col
    assert bounds.min_y >= min_row
    assert bounds.max_y <= max_row
    assert tile_bounds.min_x <= bounds.min_x
    assert tile_bounds.max_x >= bounds.max_x


def test_cli_accepts_geopf_coordinate_commands() -> None:
    parser = build_parser()

    center_args = parser.parse_args(
        [
            "geopf-center",
            "--tilematrix",
            "11",
            "--lat",
            "46.2",
            "--lon",
            "2.2",
            "--radius",
            "2",
        ]
    )
    bbox_args = parser.parse_args(
        [
            "geopf-bbox",
            "--tilematrix",
            "11",
            "--lat-min",
            "42",
            "--lon-min",
            "-5.5",
            "--lat-max",
            "51.5",
            "--lon-max",
            "8.5",
        ]
    )

    assert center_args.command == "geopf-center"
    assert bbox_args.command == "geopf-bbox"
