"""Independent, organised geographic fixtures and offline algorithm checks."""

from __future__ import annotations

import builtins
import gzip
import hashlib
import json
import os
import sys
import urllib.error
import zipfile
from pathlib import Path

import pytest

import epsm_data.climate_zones as climate

FIXTURES = Path(__file__).parent / "fixtures" / "climate_zones"
SYNTHETIC = FIXTURES / "synthetic_boundaries.json"


def point(x, y):
    return (500_000 + x, 6_500_000 + y)


def polygon(x1, y1, x2, y2):
    return {
        "type": "Polygon",
        "coordinates": [
            [point(x1, y1), point(x2, y1), point(x2, y2), point(x1, y2), point(x1, y1)]
        ],
    }


@pytest.mark.parametrize(
    "offset,expected",
    [
        ((500, 500), "SE.Zone1"),
        ((1500, 500), "SE.Zone2"),
        ((2500, 500), "SE.Zone3"),
        ((4200, 200), "SE.Zone3"),
        ((150, 150), None),
        ((3500, 500), None),
    ],
)
def test_points_holes_and_multipart_from_organised_fixture(offset, expected):
    assert climate.climate_zone_for_point(*point(*offset), boundaries_path=SYNTHETIC) == expected


@pytest.mark.parametrize("offset", [(1000, 500), (0, 500), (100, 150), (1000.0005, 500)])
def test_exact_boundary_is_explicitly_ambiguous(offset):
    with pytest.raises(climate.AmbiguousClimateZoneError, match="boundary"):
        climate.climate_zone_for_point(*point(*offset), boundaries_path=SYNTHETIC)


@pytest.mark.parametrize(
    "coords",
    [
        (18.06, 59.33),
        (6_500_000, 500_000),
        (float("nan"), 6500000),
        (True, 6500000),
        (500000, float("inf")),
        ("500000", 6500000),
    ],
)
def test_invalid_or_wrong_axis_coordinates_rejected(coords):
    with pytest.raises(ValueError, match="EPSG:3006"):
        climate.climate_zone_for_point(*coords, boundaries_path=SYNTHETIC)


def test_footprint_geo_interface_and_point():
    class Building:
        __geo_interface__ = polygon(300, 300, 400, 400)

    assert climate.climate_zone_for_building(Building(), boundaries_path=SYNTHETIC) == "SE.Zone1"
    assert (
        climate.climate_zone_for_building(
            {"type": "Point", "coordinates": point(1500, 500)}, boundaries_path=SYNTHETIC
        )
        == "SE.Zone2"
    )
    assert (
        climate.climate_zone_for_building(polygon(3300, 200, 3400, 300), boundaries_path=SYNTHETIC)
        is None
    )


def test_straddling_footprint_rejected():
    with pytest.raises(climate.AmbiguousClimateZoneError):
        climate.climate_zone_for_building(polygon(900, 400, 1100, 600), boundaries_path=SYNTHETIC)


def test_footprint_crossing_hole_with_all_vertices_inside_rejected():
    with pytest.raises(climate.AmbiguousClimateZoneError):
        climate.climate_zone_for_building(polygon(50, 125, 250, 175), boundaries_path=SYNTHETIC)


def test_footprint_enclosing_hole_with_no_edge_crossing_rejected():
    with pytest.raises(climate.AmbiguousClimateZoneError):
        climate.climate_zone_for_building(polygon(50, 50, 250, 250), boundaries_path=SYNTHETIC)


def test_multipart_building_must_share_one_zone():
    shape = {
        "type": "MultiPolygon",
        "coordinates": [
            polygon(300, 300, 400, 400)["coordinates"],
            polygon(1500, 300, 1600, 400)["coordinates"],
        ],
    }
    with pytest.raises(climate.AmbiguousClimateZoneError):
        climate.climate_zone_for_building(shape, boundaries_path=SYNTHETIC)


@pytest.mark.parametrize(
    "shape",
    [
        {"type": "Polygon", "coordinates": []},
        {"type": "Polygon", "coordinates": [[point(1, 1), point(2, 2), point(3, 3)]]},
        {"type": "LineString", "coordinates": [point(1, 1), point(2, 2)]},
        {"type": "Feature", "geometry": None},
        {"type": "Feature", "crs": "EPSG:4326", "geometry": polygon(300, 300, 400, 400)},
    ],
)
def test_invalid_building_geometry_rejected(shape):
    with pytest.raises(ValueError):
        climate.climate_zone_for_building(shape, boundaries_path=SYNTHETIC)


def test_simplified_data_has_explicit_boundary_guard(tmp_path):
    data = json.loads(SYNTHETIC.read_text())
    data["boundary_tolerance_m"] = 100
    path = tmp_path / "simplified.json"
    path.write_text(json.dumps(data))
    with pytest.raises(climate.AmbiguousClimateZoneError, match="100 m"):
        climate.climate_zone_for_point(*point(950, 500), boundaries_path=path)


def test_lookup_does_not_import_gis_or_use_network(monkeypatch):
    original = builtins.__import__

    def no_gis(name, *args, **kwargs):
        if name.split(".")[0] in {"geopandas", "shapely", "pyproj", "fiona", "pyogrio"}:
            raise AssertionError("GIS import in offline lookup")
        return original(name, *args, **kwargs)

    def no_network(*args, **kwargs):
        raise AssertionError("Network in offline lookup")

    monkeypatch.setattr(builtins, "__import__", no_gis)
    monkeypatch.setattr(climate.urllib.request, "urlopen", no_network)
    assert climate.climate_zone_for_point(*point(500, 500), boundaries_path=SYNTHETIC) == "SE.Zone1"


@pytest.mark.parametrize(
    "county,zone",
    [
        (25, "SE.Zone1"),
        ("24", "SE.Zone1"),
        ("Jämtlands län", "SE.Zone1"),
        ("Värmlands län", "SE.Zone2"),
        ("Dalarnas län", "SE.Zone2"),
        ("Gävleborgs län", "SE.Zone2"),
        ("Västernorrlands län", "SE.Zone2"),
        (1, "SE.Zone3"),
        ("Västra Götalands län", "SE.Zone3"),
    ],
)
def test_county_mapping(county, zone):
    assert climate.climate_zone_for_county(county) == zone


@pytest.mark.parametrize("county", [True, None, "unknown county", "99", 2])
def test_unknown_county_not_silently_zone_three(county):
    with pytest.raises(ValueError):
        climate.climate_zone_for_county(county)


def test_known_point_fixture_county_mapping_is_independent():
    for case in json.loads((FIXTURES / "known_points.json").read_text())["cases"]:
        if case["county_code"]:
            assert climate.climate_zone_for_county(case["county_code"]) == case["expected_zone"]


def test_missing_offline_snapshot_gives_actionable_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="official county GeoPackage/ZIP"):
        climate.climate_zone_for_point(*point(500, 500), boundaries_path=tmp_path / "missing.json")


def test_read_gzip_and_reject_wrong_crs(tmp_path):
    data = json.loads(SYNTHETIC.read_text())
    path = tmp_path / "boundaries.json.gz"
    path.write_bytes(gzip.compress(json.dumps(data).encode()))
    assert climate.climate_zone_for_point(*point(500, 500), boundaries_path=path) == "SE.Zone1"
    data["crs"] = "EPSG:4326"
    other = tmp_path / "wrong.json"
    other.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="EPSG:3006"):
        climate.climate_zone_for_point(*point(500, 500), boundaries_path=other)


def make_county_gpkg(tmp_path, *, layer="Lan", crs=3006, code_field=True, omit_county=None):
    gpd = pytest.importorskip("geopandas")
    shapely = pytest.importorskip("shapely.geometry")
    records = []
    for index, (code, name) in enumerate(climate._COUNTIES.items()):
        if code == omit_county:
            continue
        records.append(
            {
                "lankod" if code_field else "LnNamn": code if code_field else name,
                "geometry": shapely.box(
                    500000 + index * 1000, 6500000, 500500 + index * 1000, 6500500
                ),
            }
        )
    frame = gpd.GeoDataFrame(records, crs=3006)
    if crs != 3006:
        frame = frame.to_crs(crs)
    path = tmp_path / "counties.gpkg"
    frame.to_file(path, layer=layer, driver="GPKG")
    return path


def test_builder_local_gpkg_reprojects_and_records_provenance(tmp_path):
    source = make_county_gpkg(tmp_path, crs=3857, code_field=False)
    output = climate.build_climate_zone_boundaries(tmp_path / "zones.json.gz", source_path=source)
    document = json.loads(gzip.decompress(output.read_bytes()))
    assert document["crs"] == "EPSG:3006"
    assert document["source"]["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert document["source"]["layer"] == "Lan"
    assert document["simplify_tolerance_m"] == 0
    assert len(document["county_to_zone"]) == 21
    assert {zone["id"] for zone in document["zones"]} == {"SE.Zone1", "SE.Zone2", "SE.Zone3"}
    assert climate.climate_zone_for_point(500250, 6500250, boundaries_path=output) == "SE.Zone3"


def test_builder_extracts_only_gpkg_safely_and_supports_mock_download(tmp_path, monkeypatch):
    source = make_county_gpkg(tmp_path)
    archive = tmp_path / "counties.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        stream.write(source, "../../counties.gpkg")
        stream.writestr("../../must-not-extract.txt", "malicious")
    monkeypatch.setattr(climate.urllib.request, "urlopen", lambda *a, **k: archive.open("rb"))
    output = climate.build_climate_zone_boundaries(
        tmp_path / "zones.json", simplify_tolerance_m=100
    )
    assert json.loads(output.read_text())["boundary_tolerance_m"] == 100
    assert not (tmp_path.parent / "must-not-extract.txt").exists()


def test_builder_authentication_failure_does_not_fallback(tmp_path, monkeypatch):
    pytest.importorskip("geopandas")

    def unauthorized(*args, **kwargs):
        raise urllib.error.HTTPError(climate.DEFAULT_SOURCE_URL, 401, "Unauthorized", {}, None)

    monkeypatch.setattr(climate.urllib.request, "urlopen", unauthorized)
    with pytest.raises(RuntimeError, match="authorised access"):
        climate.build_climate_zone_boundaries(tmp_path / "zones.json")
    assert not (tmp_path / "zones.json").exists()


def test_builder_rejects_ambiguous_archive_and_absent_counties(tmp_path):
    pytest.importorskip("geopandas")
    archive = tmp_path / "multiple.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr("one.gpkg", "")
        stream.writestr("two.gpkg", "")
    with pytest.raises(ValueError, match="exactly one GeoPackage"):
        climate.build_climate_zone_boundaries(tmp_path / "zones.json", source_path=archive)
    source = make_county_gpkg(tmp_path, omit_county="25")
    with pytest.raises(ValueError, match="all 21"):
        climate.build_climate_zone_boundaries(tmp_path / "zones.json", source_path=source)


def test_builder_missing_optional_dependency_has_clear_error(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "geopandas", None)
    with pytest.raises(ImportError, match="offline lookup has no GIS dependencies"):
        climate.build_climate_zone_boundaries(tmp_path / "zones.json")


def test_known_geographic_points_against_bundled_scb_snapshot():
    snapshot = os.environ.get("EPSM_CLIMATE_ZONE_BOUNDARIES")
    for case in json.loads((FIXTURES / "known_points.json").read_text())["cases"]:
        actual = climate.climate_zone_for_point(
            case["easting"], case["northing"], boundaries_path=snapshot
        )
        assert actual == case["expected_zone"], case["name"]


def test_footprint_edge_boundary_guard_includes_non_overlapping_boxes(tmp_path):
    data = json.loads(SYNTHETIC.read_text())
    data["boundary_tolerance_m"] = 100.1
    data["zones"][0]["geometry"]["coordinates"][1] = polygon(450, 450, 550, 550)["coordinates"][0]
    path = tmp_path / "guarded.json"
    path.write_text(json.dumps(data))
    with pytest.raises(climate.AmbiguousClimateZoneError, match="boundary"):
        climate.climate_zone_for_building(polygon(200, 650, 800, 700), boundaries_path=path)


def test_bundled_snapshot_has_declared_source_and_no_added_simplification():
    expected = json.loads((FIXTURES / "scb_source.json").read_text())
    raw = (
        climate.files("epsm_data.datasets.climate_zones")
        .joinpath("boundaries.json.gz")
        .read_bytes()
    )
    actual = json.loads(gzip.decompress(raw))
    assert actual["source"]["url"] == expected["source_url"]
    assert actual["source"]["sha256"] == expected["source_archive_sha256"]
    assert actual["source"]["archive_member"] == expected["source_county_member"]
    assert actual["source"]["provider"] == expected["source_provider"]
    assert actual["source"]["generalised"] is True
    assert actual["source"]["license"] == expected["license"]
    assert actual["simplify_tolerance_m"] == expected["additional_simplification_m"]
    assert actual["boundary_tolerance_m"] == expected["default_boundary_guard_m"]
    assert len(actual["county_to_zone"]) == expected["source_county_count"]


def test_nested_scb_shapefile_builder_and_provenance(tmp_path):
    gpd = pytest.importorskip("geopandas")
    gpkg = make_county_gpkg(tmp_path)
    folder = tmp_path / "shape"
    folder.mkdir()
    shape = folder / "Lan_Sweref99TM_region.shp"
    gpd.read_file(gpkg, layer="Lan").rename(columns={"lankod": "LnKod"}).to_file(shape)
    inner = tmp_path / "LanSweref99TM.zip"
    with zipfile.ZipFile(inner, "w") as archive:
        for part in folder.iterdir():
            archive.write(part, "../" + part.name)
    outer = tmp_path / "shape_svenska.zip"
    with zipfile.ZipFile(outer, "w") as archive:
        archive.write(inner, inner.name)
        archive.writestr("Kommun_Sweref99TM.zip", "not selected")
        archive.writestr("LAomraden_2024_Sweref99tm.zip", "not selected")
    output = climate.build_climate_zone_boundaries(
        tmp_path / "scb.json.gz", source_path=outer, url=climate.SCB_SOURCE_URL
    )
    data = json.loads(gzip.decompress(output.read_bytes()))
    assert data["source"]["provider"] == "Statistics Sweden (SCB)"
    assert data["source"]["license"] == "CC0"
    assert data["source"]["generalised"] is True
    assert data["source"]["archive_member"] == "LanSweref99TM.zip/../Lan_Sweref99TM_region.shp"
    assert data["boundary_tolerance_m"] == 100
    assert climate.climate_zone_for_point(500250, 6500250, boundaries_path=output) == "SE.Zone3"


def test_shapefile_archive_requires_projection_sidecar(tmp_path):
    pytest.importorskip("geopandas")
    archive = tmp_path / "incomplete.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        for suffix in (".shp", ".dbf", ".shx"):
            stream.writestr("Lan_region" + suffix, "")
    with pytest.raises(ValueError, match=".prj companion"):
        climate.build_climate_zone_boundaries(tmp_path / "out.json", source_path=archive)
