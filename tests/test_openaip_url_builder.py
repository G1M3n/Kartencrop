from kartencrop.openaip import OPENAIP_STYLE_TEMPLATE, TileRequest


def test_tile_request_url_without_key() -> None:
    req = TileRequest(layer="openaip", z=8, x=134, y=84)
    assert req.vector_url() == "https://api.tiles.openaip.net/api/data/openaip/8/134/84.pbf"


def test_tile_request_url_with_key() -> None:
    req = TileRequest(layer="openaip", z=8, x=134, y=84)
    assert req.vector_url("abc123").endswith("/data/openaip/8/134/84.pbf?apiKey=abc123")


def test_raster_url_with_key() -> None:
    req = TileRequest(layer="hotspots", z=8, x=134, y=84)
    assert req.raster_url("abc123").endswith("/data/hotspots/8/134/84.png?apiKey=abc123")


def test_style_template() -> None:
    assert OPENAIP_STYLE_TEMPLATE.format(style="openaip-default-style").endswith("/styles/openaip-default-style.json")
