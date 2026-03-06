from kartencrop.swissgeo import (
    SWISS_CLOSURES_LAYER,
    SWISS_WMS_LAYER_PRESETS,
    SwissIdentifyRequest,
    SwissWmsRequest,
    bbox_from_center,
    bbox_from_wgs84_bounds,
    bbox_from_wgs84_center,
    dimensions_from_bbox_long_edge,
    merge_layers,
    parse_bbox,
    remove_layer,
    scaled_dimensions,
    wgs84_to_lv95,
)


def test_bbox_from_center() -> None:
    bbox = bbox_from_center(2626772.3, 1178584.47, 10000, 8000)
    assert bbox.min_x == 2621772.3
    assert bbox.max_x == 2631772.3
    assert bbox.min_y == 1174584.47
    assert bbox.max_y == 1182584.47


def test_parse_bbox() -> None:
    bbox = parse_bbox("2600000,1200000,2610000,1210000")
    assert bbox.as_wms_bbox() == "2600000.0,1200000.0,2610000.0,1210000.0"


def test_scaled_dimensions_caps_width() -> None:
    width, height = scaled_dimensions(4000, 2000, max_width=1400)
    assert width == 1400
    assert height == 700


def test_dimensions_from_bbox_long_edge_for_wide_bbox() -> None:
    bbox = bbox_from_center(2626772.3, 1178584.47, 10000, 5000)
    width, height = dimensions_from_bbox_long_edge(bbox, 2000)
    assert width == 2000
    assert height == 1000


def test_wgs84_to_lv95_for_bern() -> None:
    east, north = wgs84_to_lv95(46.95108, 7.43864)
    assert round(east, 0) == 2600001
    assert round(north, 0) == 1200000


def test_bbox_from_wgs84_center() -> None:
    bbox = bbox_from_wgs84_center(46.95108, 7.43864, 1000, 2000)
    assert round(bbox.width_m, 0) == 1000
    assert round(bbox.height_m, 0) == 2000


def test_bbox_from_wgs84_bounds() -> None:
    bbox = bbox_from_wgs84_bounds(46.9, 7.3, 47.0, 7.5)
    assert bbox.max_x > bbox.min_x
    assert bbox.max_y > bbox.min_y


def test_wms_request_params_with_time() -> None:
    request = SwissWmsRequest(
        layers=SWISS_WMS_LAYER_PRESETS["wanderkarte"],
        bbox=parse_bbox("2600000,1200000,2610000,1210000"),
        width=1024,
        height=768,
        image_format="image/png",
        transparent=True,
        time="1864",
    )
    params = request.params()

    assert params["SERVICE"] == "WMS"
    assert params["REQUEST"] == "GetMap"
    assert params["LAYERS"] == "ch.swisstopo.pixelkarte-farbe,ch.swisstopo.swisstlm3d-wanderwege"
    assert params["CRS"] == "EPSG:2056"
    assert params["BBOX"] == "2600000.0,1200000.0,2610000.0,1210000.0"
    assert params["WIDTH"] == "1024"
    assert params["HEIGHT"] == "768"
    assert params["FORMAT"] == "image/png"
    assert params["TRANSPARENT"] == "TRUE"
    assert params["TIME"] == "1864"


def test_merge_and_remove_layers() -> None:
    merged = merge_layers("a,b", SWISS_CLOSURES_LAYER, "b")
    assert merged == f"a,b,{SWISS_CLOSURES_LAYER}"
    assert remove_layer(merged, SWISS_CLOSURES_LAYER) == "a,b"


def test_identify_request_params() -> None:
    request = SwissIdentifyRequest(
        map_extent=parse_bbox("2600000,1200000,2610000,1210000"),
        geometry_x=2605000,
        geometry_y=1205000,
        image_width=1000,
        image_height=800,
        tolerance=12,
    )
    params = request.params()
    assert params["layers"] == f"all:{SWISS_CLOSURES_LAYER}"
    assert params["geometry"] == "2605000,1205000"
    assert params["mapExtent"] == "2600000.0,1200000.0,2610000.0,1210000.0"
    assert params["imageDisplay"] == "1000,800,96"
    assert params["sr"] == "2056"
