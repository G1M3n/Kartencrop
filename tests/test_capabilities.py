from pathlib import Path
import shutil
import uuid

from kartencrop.capabilities import (
    DEFAULT_GEOPF_SCAN_OACI_LIMITS,
    GeoPfCapabilities,
    _persist_capabilities_to_cache,
    _load_capabilities_from_cache,
    parse_geopf_capabilities_xml,
)


SAMPLE_WMTS_CAPABILITIES = """<?xml version="1.0" encoding="UTF-8"?>
<Capabilities xmlns="http://www.opengis.net/wmts/1.0" xmlns:ows="http://www.opengis.net/ows/1.1">
  <Contents>
    <Layer>
      <ows:Identifier>GEOGRAPHICALGRIDSYSTEMS.MAPS.SCAN-OACI</ows:Identifier>
      <TileMatrixSetLink>
        <TileMatrixSet>PM</TileMatrixSet>
        <TileMatrixSetLimits>
          <TileMatrixLimits>
            <TileMatrix>PM:10</TileMatrix>
            <MinTileRow>340</MinTileRow>
            <MaxTileRow>386</MaxTileRow>
            <MinTileCol>494</MinTileCol>
            <MaxTileCol>543</MaxTileCol>
          </TileMatrixLimits>
          <TileMatrixLimits>
            <TileMatrix>PM:11</TileMatrix>
            <MinTileRow>681</MinTileRow>
            <MaxTileRow>772</MaxTileRow>
            <MinTileCol>989</MinTileCol>
            <MaxTileCol>1087</MaxTileCol>
          </TileMatrixLimits>
        </TileMatrixSetLimits>
      </TileMatrixSetLink>
    </Layer>
  </Contents>
</Capabilities>
"""


def test_parse_geopf_capabilities_xml_extracts_limits() -> None:
    limits = parse_geopf_capabilities_xml(SAMPLE_WMTS_CAPABILITIES)
    assert limits == {
        10: (494, 543, 340, 386),
        11: (989, 1087, 681, 772),
    }


def test_parse_geopf_capabilities_xml_rejects_missing_layer() -> None:
    xml = SAMPLE_WMTS_CAPABILITIES.replace("GEOGRAPHICALGRIDSYSTEMS.MAPS.SCAN-OACI", "OTHER")
    try:
        parse_geopf_capabilities_xml(xml)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for missing layer")


def test_capabilities_cache_roundtrip(monkeypatch) -> None:
    tmp_path = Path.cwd() / "outputs" / "test_cache" / f"case_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    try:
        target = tmp_path / "geopf_scan_oaci_limits.json"
        capabilities = GeoPfCapabilities(limits=DEFAULT_GEOPF_SCAN_OACI_LIMITS, source="live", fetched_at=123.0)

        import kartencrop.capabilities as capabilities_module

        monkeypatch.setattr(capabilities_module, "GEOPF_CAPABILITIES_CACHE_PATH", target)
        _persist_capabilities_to_cache(capabilities)
        loaded = _load_capabilities_from_cache(allow_stale=True)

        assert loaded is not None
        assert loaded.limits == DEFAULT_GEOPF_SCAN_OACI_LIMITS
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
