from kartencrop.geo import bbox_to_tile_bounds, latlon_to_tile, tile_bounds_to_geo_bounds


def test_latlon_to_tile_goettingen_z12() -> None:
    tile = latlon_to_tile(51.5413, 9.9158, 12)
    assert tile.z == 12
    assert 2100 <= tile.x <= 2200
    assert 1300 <= tile.y <= 1400


def test_bbox_to_tile_bounds_order() -> None:
    bounds = bbox_to_tile_bounds(51.4, 9.7, 51.8, 10.2, 10)
    assert bounds.min_x <= bounds.max_x
    assert bounds.min_y <= bounds.max_y
    assert bounds.width > 0
    assert bounds.height > 0


def test_tile_bounds_to_geo_bounds_covers_requested_bbox() -> None:
    requested = (51.4, 9.7, 51.8, 10.2)
    tile_bounds = bbox_to_tile_bounds(*requested, 10)
    geo_bounds = tile_bounds_to_geo_bounds(tile_bounds)

    assert geo_bounds.lat_min <= requested[0]
    assert geo_bounds.lon_min <= requested[1]
    assert geo_bounds.lat_max >= requested[2]
    assert geo_bounds.lon_max >= requested[3]


def test_tile_bounds_to_geo_bounds_changes_with_zoom() -> None:
    requested = (52.48, 13.35, 52.56, 13.48)
    low_zoom_bounds = tile_bounds_to_geo_bounds(bbox_to_tile_bounds(*requested, 8))
    high_zoom_bounds = tile_bounds_to_geo_bounds(bbox_to_tile_bounds(*requested, 11))

    low_zoom_width = low_zoom_bounds.lon_max - low_zoom_bounds.lon_min
    high_zoom_width = high_zoom_bounds.lon_max - high_zoom_bounds.lon_min

    assert high_zoom_width < low_zoom_width
