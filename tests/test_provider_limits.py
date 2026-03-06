import pytest

from kartencrop.providers import (
    GEOPF_MAX_TILEMATRIX,
    GEOPF_MIN_TILEMATRIX,
    GEOPF_SCAN_OACI_LIMITS,
    OFM_FINLAND_TILE_LIMITS,
    OFM_MAX_ZOOM,
    OFM_MIN_ZOOM,
    OPENAIP_MAX_ZOOM,
    OpenAipRasterProvider,
    OpenFlightMapsProvider,
    GeoPfProvider,
)


def test_ofm_provider_validates_zoom_range() -> None:
    OpenFlightMapsProvider(zoom=OFM_MIN_ZOOM)
    OpenFlightMapsProvider(zoom=OFM_MAX_ZOOM)
    with pytest.raises(ValueError):
        OpenFlightMapsProvider(zoom=OFM_MIN_ZOOM - 1)
    with pytest.raises(ValueError):
        OpenFlightMapsProvider(zoom=OFM_MAX_ZOOM + 1)


def test_geopf_provider_validates_tilematrix_range() -> None:
    GeoPfProvider(tilematrix=str(GEOPF_MIN_TILEMATRIX))
    GeoPfProvider(tilematrix=str(GEOPF_MAX_TILEMATRIX))
    with pytest.raises(ValueError):
        GeoPfProvider(tilematrix=str(GEOPF_MIN_TILEMATRIX - 1))
    with pytest.raises(ValueError):
        GeoPfProvider(tilematrix=str(GEOPF_MAX_TILEMATRIX + 1))


def test_openaip_provider_validates_zoom_range() -> None:
    OpenAipRasterProvider(zoom=1)
    OpenAipRasterProvider(zoom=OPENAIP_MAX_ZOOM)
    with pytest.raises(ValueError):
        OpenAipRasterProvider(zoom=0)
    with pytest.raises(ValueError):
        OpenAipRasterProvider(zoom=OPENAIP_MAX_ZOOM + 1)


def test_known_tile_limit_tables_are_consistent() -> None:
    assert set(OFM_FINLAND_TILE_LIMITS) == set(range(OFM_MIN_ZOOM, OFM_MAX_ZOOM + 1))
    assert set(GEOPF_SCAN_OACI_LIMITS) == set(range(GEOPF_MIN_TILEMATRIX, GEOPF_MAX_TILEMATRIX + 1))
