from __future__ import annotations

import os

import pytest

from kartencrop.openaip import fetch_style
from kartencrop.providers import GeoPfProvider, OpenAipRasterProvider, OpenFlightMapsProvider


pytestmark = pytest.mark.live
LIVE_ENABLED = os.getenv("RUN_LIVE_TESTS") == "1"


@pytest.mark.skipif(not LIVE_ENABLED, reason="live tests disabled")
def test_live_ofm_probe_tile() -> None:
    provider = OpenFlightMapsProvider(zoom=8, chart_type="aero")
    image = provider.fetch_tile(137, 83)
    assert image is not None


@pytest.mark.skipif(not LIVE_ENABLED, reason="live tests disabled")
def test_live_geopf_probe_tile() -> None:
    provider = GeoPfProvider(tilematrix="11")
    image = provider.fetch_tile(1037, 704)
    assert image is not None


@pytest.mark.skipif(not LIVE_ENABLED, reason="live tests disabled")
def test_live_openaip_style_fetch() -> None:
    result = fetch_style("openaip-default-style")
    assert result.ok


@pytest.mark.skipif(not LIVE_ENABLED, reason="live tests disabled")
def test_live_openaip_probe_tile_requires_api_key() -> None:
    api_key = os.getenv("OPENAIP_API_KEY")
    if not api_key:
        pytest.skip("OPENAIP_API_KEY not set")
    provider = OpenAipRasterProvider(zoom=9, layer="openaip", api_key=api_key)
    image = provider.fetch_tile(275, 167)
    assert image is not None
