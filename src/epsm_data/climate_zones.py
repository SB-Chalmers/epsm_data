"""Offline county-based climate-zone lookup for SWEREF 99 TM (EPSG:3006).

Coordinates are always (easting, northing), in metres.  The three zones are
catalogue selections, not a determination of the regulations applicable to a
particular building. Bundled SCB boundaries are generalised screening data,
not survey-precise geometry. Lookup never downloads data or imports GIS packages.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import numbers
import shutil
import sqlite3
import tempfile
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any, Mapping

LANTMATERIET_SOURCE_URL = (
    "https://dl1-ver.lantmateriet.se/administrativ-indelning/kommun-lan-rike/"
    "kommun-lan-rike_aktuell.zip"
)
SCB_SOURCE_URL = (
    "https://www.scb.se/contentassets/3443fea3fa6640f7a57ea15d9a372d33/shape_svenska_260225.zip"
)
SCB_METADATA_URL = (
    "https://www.scb.se/hitta-statistik/regional-statistik-och-kartor/"
    "regionala-indelningar/digitala-granser/"
)
DEFAULT_SOURCE_URL = SCB_SOURCE_URL
_COUNTIES = {
    "01": "Stockholms län",
    "03": "Uppsala län",
    "04": "Södermanlands län",
    "05": "Östergötlands län",
    "06": "Jönköpings län",
    "07": "Kronobergs län",
    "08": "Kalmar län",
    "09": "Gotlands län",
    "10": "Blekinge län",
    "12": "Skåne län",
    "13": "Hallands län",
    "14": "Västra Götalands län",
    "17": "Värmlands län",
    "18": "Örebro län",
    "19": "Västmanlands län",
    "20": "Dalarnas län",
    "21": "Gävleborgs län",
    "22": "Västernorrlands län",
    "23": "Jämtlands län",
    "24": "Västerbottens län",
    "25": "Norrbottens län",
}
_ZONE_CODES = {
    code: "SE.Zone1"
    if code in {"23", "24", "25"}
    else "SE.Zone2"
    if code in {"17", "20", "21", "22"}
    else "SE.Zone3"
    for code in _COUNTIES
}


def climate_zone_for_county(county: str | int) -> str:
    """Resolve an official two-digit county code or Swedish county name."""
    if isinstance(county, bool) or not isinstance(county, (str, int)):
        raise ValueError("Expected a Swedish county code or name.")
    return (
        _ZONE_CODES[_county_code({"LnNamn": county}, ["LnNamn"])]
        if not str(county).isdigit()
        else _ZONE_CODES[_county_code({"lankod": county}, ["lankod"])]
    )


class AmbiguousClimateZoneError(ValueError):
    """A point or footprint cannot be assigned to one unambiguous zone."""


def _coordinate(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError("EPSG:3006 coordinates must be finite real numbers in metres.")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("EPSG:3006 coordinates must be finite real numbers in metres.")
    return value


def _point(value: Any) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        raise ValueError("Expected EPSG:3006 coordinates (easting, northing).")
    x, y = _coordinate(value[0]), _coordinate(value[1])
    # This catches latitude/longitude, reversed Swedish axes and obvious CRS errors.
    # Valid projected coordinates outside Sweden still return None.
    if not (0 <= x <= 1_500_000 and 5_000_000 <= y <= 9_000_000):
        raise ValueError("Expected EPSG:3006 metres in (easting, northing) order.")
    return x, y


def _bbox(ring: Any) -> tuple[float, float, float, float]:
    return (
        min(p[0] for p in ring),
        min(p[1] for p in ring),
        max(p[0] for p in ring),
        max(p[1] for p in ring),
    )


def _in_box(point: tuple[float, float], box: Any, padding: float = 0) -> bool:
    return (
        box[0] - padding <= point[0] <= box[2] + padding
        and box[1] - padding <= point[1] <= box[3] + padding
    )


def _distance_segment(p: Any, a: Any, b: Any) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = dx * dx + dy * dy
    t = 0 if length == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def _ring_relation(point: Any, ring: Any, tolerance: float) -> int:
    """Return 0 outside, 1 inside, 2 on/within tolerance of a boundary."""
    if not _in_box(point, _bbox(ring), tolerance):
        return 0
    inside = False
    x, y = point
    for a, b in zip(ring, ring[1:]):
        if _distance_segment(point, a, b) <= tolerance:
            return 2
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
            inside = not inside
    return int(inside)


def _polygon_relation(point: Any, polygon: Any, tolerance: float) -> int:
    exterior = _ring_relation(point, polygon[0], tolerance)
    if exterior != 1:
        return exterior
    for hole in polygon[1:]:
        relation = _ring_relation(point, hole, tolerance)
        if relation == 2:
            return 2
        if relation == 1:
            return 0
    return 1


def _polygons(geometry: Mapping[str, Any]) -> Any:
    if geometry.get("type") == "Polygon":
        return [geometry["coordinates"]]
    if geometry.get("type") == "MultiPolygon":
        return geometry["coordinates"]
    raise ValueError("Boundary and building geometry must be Polygon or MultiPolygon.")


@lru_cache(maxsize=8)
def _load_boundaries(path: str | None) -> tuple[Any, float]:
    resource = (
        Path(path)
        if path
        else files("epsm_data.datasets.climate_zones").joinpath("boundaries.json.gz")
    )
    try:
        with resource.open("rb") as stream:
            raw = stream.read()
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            "Climate-zone boundary data is unavailable. Build it from an official county "
            "GeoPackage/ZIP and pass boundaries_path to the lookup helper."
        ) from exc
    document = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    if document.get("schema_version") != 1 or document.get("crs") != "EPSG:3006":
        raise ValueError("Boundary data must use schema_version 1 and EPSG:3006.")
    zones = []
    for feature in document["zones"]:
        if feature["id"] not in {"SE.Zone1", "SE.Zone2", "SE.Zone3"}:
            raise ValueError("Unrecognised climate-zone identifier in boundary data.")
        polygons = _polygons(feature["geometry"])
        for polygon in polygons:
            for ring in polygon:
                if len(ring) < 4 or ring[0] != ring[-1]:
                    raise ValueError(
                        "Boundary polygon rings must contain four points and be closed."
                    )
        zones.append((feature["id"], polygons))
    if {zone for zone, _ in zones} != {"SE.Zone1", "SE.Zone2", "SE.Zone3"}:
        raise ValueError("Boundary data must contain all three catalogue zones.")
    tolerance = float(document.get("boundary_tolerance_m", document.get("simplify_tolerance_m", 0)))
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("Boundary tolerance must be finite and non-negative.")
    return tuple(zones), max(tolerance, 0.001)


def _lookup(point: Any, boundaries: Any) -> str | None:
    zones, tolerance = boundaries
    matches, edges = set(), set()
    for zone, polygons in zones:
        for polygon in polygons:
            relation = _polygon_relation(point, polygon, tolerance)
            if relation == 2:
                edges.add(zone)
            elif relation == 1:
                matches.add(zone)
    if edges:
        raise AmbiguousClimateZoneError(
            "Point is on or too close to a zone/country boundary for a reliable assignment "
            f"(boundary guard {tolerance:g} m; candidate zones: {', '.join(sorted(matches | edges))})."
        )
    if len(matches) > 1:
        raise AmbiguousClimateZoneError("Boundary polygons overlap across climate zones.")
    return next(iter(matches), None)


def climate_zone_for_point(
    easting: float, northing: float, *, boundaries_path: str | Path | None = None
) -> str | None:
    """Return ``SE.Zone1/2/3`` or None outside the bundled Swedish polygons.

    No coordinate transformation is attempted. Exact boundaries, and points
    within the dataset's declared boundary guard, raise AmbiguousClimateZoneError.
    """
    point = _point((easting, northing))
    return _lookup(
        point, _load_boundaries(str(Path(boundaries_path).resolve()) if boundaries_path else None)
    )


def _cross(a: Any, b: Any, c: Any) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(a: Any, b: Any, c: Any, d: Any) -> bool:
    if (
        max(a[0], b[0]) < min(c[0], d[0])
        or max(c[0], d[0]) < min(a[0], b[0])
        or max(a[1], b[1]) < min(c[1], d[1])
        or max(c[1], d[1]) < min(a[1], b[1])
    ):
        return False
    return _cross(a, b, c) * _cross(a, b, d) <= 0 and _cross(c, d, a) * _cross(c, d, b) <= 0


def _segments_distance(a: Any, b: Any, c: Any, d: Any) -> float:
    if _segments_intersect(a, b, c, d):
        return 0.0
    return min(
        _distance_segment(a, c, d),
        _distance_segment(b, c, d),
        _distance_segment(c, a, b),
        _distance_segment(d, a, b),
    )


def climate_zone_for_building(
    geometry: Any, *, boundaries_path: str | Path | None = None
) -> str | None:
    """Assign an EPSG:3006 Point, Polygon or MultiPolygon geo-interface object.

    All footprint vertices and edges must stay within the same zone. A footprint
    crossing a zone/country boundary raises instead of selecting a random vertex
    or a centroid outside a concave footprint. An entirely outside footprint
    returns None. Shapely objects work through ``__geo_interface__``; no Shapely
    import is required. Geometry must already use EPSG:3006.
    """
    if hasattr(geometry, "__geo_interface__"):
        geometry = geometry.__geo_interface__
    if not isinstance(geometry, Mapping):
        raise ValueError("Expected a GeoJSON geometry or an object with __geo_interface__.")
    feature_crs = geometry.get("crs")
    if feature_crs and "3006" not in str(feature_crs):
        raise ValueError("Building geometry must already use EPSG:3006.")
    if geometry.get("type") == "Feature":
        geometry = geometry.get("geometry")
        if not isinstance(geometry, Mapping):
            raise ValueError("Building feature must contain a geometry.")
    crs = geometry.get("crs")
    if crs and "3006" not in str(crs):
        raise ValueError("Building geometry must already use EPSG:3006.")
    if geometry.get("type") == "Point":
        return climate_zone_for_point(
            *_point(geometry["coordinates"]), boundaries_path=boundaries_path
        )
    polygons = _polygons(geometry)
    if not polygons:
        raise ValueError("Building geometry cannot be empty.")
    boundaries = _load_boundaries(str(Path(boundaries_path).resolve()) if boundaries_path else None)
    matches = set()
    building_rings = []
    for polygon in polygons:
        if not polygon:
            raise ValueError("Building polygon cannot be empty.")
        for raw_ring in polygon:
            ring = [_point(p) for p in raw_ring]
            if len(ring) < 4 or ring[0] != ring[-1]:
                raise ValueError("Building polygon rings must contain four points and be closed.")
            area = abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:])))
            if area <= 1e-6:
                raise ValueError("Building polygon rings must have a non-zero area.")
            building_rings.append(ring)
            matches.update(_lookup(point, boundaries) for point in ring[:-1])
    if len(matches) != 1:
        raise AmbiguousClimateZoneError(
            "Building footprint spans multiple zones or crosses Sweden's boundary."
        )
    # A segment may exit and re-enter a concave zone even when both endpoints
    # are inside. Also detect an enclosed zone island without vertex crossings.
    for _, zone_polygons in boundaries[0]:
        for zone_polygon in zone_polygons:
            for zone_ring in zone_polygon:
                for ring in building_rings:
                    if not _boxes_overlap(_bbox(ring), _bbox(zone_ring), boundaries[1]):
                        continue
                    if any(
                        _segments_distance(a, b, c, d) <= boundaries[1]
                        for a, b in zip(ring, ring[1:])
                        for c, d in zip(zone_ring, zone_ring[1:])
                    ):
                        raise AmbiguousClimateZoneError(
                            "Building footprint crosses a zone/country boundary."
                        )
                if any(_polygon_relation(zone_ring[0], polygon, 0) == 1 for polygon in polygons):
                    raise AmbiguousClimateZoneError(
                        "Building footprint encloses a zone/country boundary."
                    )
    return next(iter(matches))


def _boxes_overlap(a: Any, b: Any, padding: float = 0) -> bool:
    return (
        a[0] <= b[2] + padding
        and b[0] <= a[2] + padding
        and a[1] <= b[3] + padding
        and b[1] <= a[3] + padding
    )


def _normalise(text: Any) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(text)).casefold() if c.isalnum())


def _county_code(row: Any, columns: Any) -> str:
    normalized = {_normalise(column): column for column in columns}
    code_columns = ("lankod", "lanskod", "lnkod", "lanid", "lansbeteckning")
    for key in code_columns:
        if key in normalized:
            raw = str(row[normalized[key]]).strip()
            if raw.endswith(".0"):
                raw = raw[:-2]
            code = raw.zfill(2)
            if code not in _COUNTIES:
                raise ValueError(f"Unrecognised Swedish county code: {raw!r}.")
            return code
    for key in ("lnnamn", "lannamn", "lansnamn", "namn"):
        if key in normalized:
            name = _normalise(row[normalized[key]])
            for code, county in _COUNTIES.items():
                if name in {_normalise(county), _normalise(county.removesuffix(" län"))}:
                    return code
            raise ValueError(f"Unrecognised Swedish county name: {row[normalized[key]]!r}.")
    raise ValueError(
        "County layer needs a recognised county-code or county-name field (such as LnNamn)."
    )


def _extract_county_archive(source: Path, temporary: Path, depth: int = 0) -> tuple[Path, str]:
    """Select one county dataset and extract only its required file cohort."""
    if depth > 2:
        raise ValueError("County archive nesting exceeds the supported two levels.")
    with zipfile.ZipFile(source) as archive:
        members = [member for member in archive.infolist() if not member.is_dir()]
        packages = [member for member in members if member.filename.lower().endswith(".gpkg")]
        shapes = [
            member
            for member in members
            if member.filename.lower().endswith(".shp")
            and _normalise(Path(member.filename).stem).startswith("lan")
        ]
        nested = [
            member
            for member in members
            if member.filename.lower().endswith(".zip")
            and _normalise(Path(member.filename).stem).startswith("lan")
        ]
        if len(packages) + len(shapes) + len(nested) != 1:
            raise ValueError(
                "Expected exactly one GeoPackage, county Shapefile or nested county ZIP in archive."
            )
        if nested:
            target = temporary / f"county_archive_{depth}.zip"
            with archive.open(nested[0]) as entry, target.open("wb") as stream:
                shutil.copyfileobj(entry, stream)
            data_file, member_name = _extract_county_archive(target, temporary, depth + 1)
            return data_file, f"{nested[0].filename}/{member_name}"
        if packages:
            target = temporary / "counties.gpkg"
            with archive.open(packages[0]) as entry, target.open("wb") as stream:
                shutil.copyfileobj(entry, stream)
            return target, packages[0].filename
        shape = shapes[0]
        stem = str(Path(shape.filename).with_suffix("")).casefold()
        for suffix in (".shp", ".dbf", ".shx", ".prj", ".cpg"):
            cohort = [member for member in members if member.filename.casefold() == stem + suffix]
            if len(cohort) != 1:
                if suffix == ".cpg" and not cohort:
                    continue
                raise ValueError(f"County Shapefile needs exactly one {suffix} companion.")
            # Archive paths never determine an output directory or filename.
            with (
                archive.open(cohort[0]) as entry,
                (temporary / f"counties{suffix}").open("wb") as stream,
            ):
                shutil.copyfileobj(entry, stream)
        return temporary / "counties.shp", shape.filename


def build_climate_zone_boundaries(
    output_path: str | Path,
    *,
    url: str = DEFAULT_SOURCE_URL,
    source_path: str | Path | None = None,
    simplify_tolerance_m: float = 0.0,
    boundary_tolerance_m: float = 100.0,
) -> Path:
    """Explicitly prepare offline zones from county GeoPackage or Shapefile data.

    GeoPandas is needed only for this refresh. ``source_path`` accepts a local
    GeoPackage, Shapefile, or ZIP. SCB's outer ZIP with a nested county Shapefile
    archive is supported. Only the selected county dataset is extracted. Pass
    its actual ``url`` with local sources to record the correct provenance.

    Default zero simplification preserves source lines. The default 100 m guard
    flags boundary uncertainty; it is not a guarantee of source accuracy. A
    supplied simplification tolerance increases the guard if necessary. Output
    is gzip JSON when the filename ends in .gz, otherwise plain JSON.
    """
    tolerance = _coordinate(simplify_tolerance_m)
    guard = _coordinate(boundary_tolerance_m)
    if tolerance < 0 or guard < 0:
        raise ValueError("Simplification and boundary tolerances cannot be negative.")
    try:
        import geopandas as gpd
    except ImportError as exc:
        raise ImportError(
            "Install epsm_data[geography] for boundary refresh; offline lookup has no GIS dependencies."
        ) from exc
    with tempfile.TemporaryDirectory(prefix="epsm-climate-zones-") as folder:
        temporary = Path(folder)
        if source_path is None:
            source = temporary / "counties.zip"
            try:
                with (
                    urllib.request.urlopen(url, timeout=120) as response,
                    source.open("wb") as target,
                ):
                    shutil.copyfileobj(response, target)
            except urllib.error.HTTPError as exc:
                if exc.code in {401, 403}:
                    raise RuntimeError(
                        "County download requires authorised access. Download the official ZIP separately and provide source_path."
                    ) from exc
                raise
        else:
            source = Path(source_path)
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        archive_member = None
        if zipfile.is_zipfile(source):
            data_file, archive_member = _extract_county_archive(source, temporary)
        elif source.suffix.lower() in {".gpkg", ".shp"}:
            data_file = source
        else:
            raise ValueError("source_path must be a county GeoPackage, Shapefile or ZIP.")
        if data_file.suffix.lower() == ".gpkg":
            with sqlite3.connect(f"file:{data_file.resolve()}?mode=ro", uri=True) as connection:
                layer_names = [
                    row[0]
                    for row in connection.execute(
                        "SELECT table_name FROM gpkg_contents WHERE data_type='features'"
                    )
                ]
            county_layers = [name for name in layer_names if _normalise(name) == "lan"]
            if len(county_layers) != 1:
                raise ValueError("Expected exactly one county layer named 'lan' or 'Lan'.")
            layer = county_layers[0]
            counties = gpd.read_file(data_file, layer=layer)
        else:
            layer = Path(archive_member or data_file.name).stem
            counties = gpd.read_file(data_file)
        if counties.crs is None:
            raise ValueError("County source is missing its coordinate reference system.")
        source_crs = str(counties.crs)
        counties = counties.to_crs(epsg=3006)
        counties["_county_code"] = [
            _county_code(row, counties.columns) for _, row in counties.iterrows()
        ]
        if set(counties["_county_code"]) != set(_COUNTIES):
            raise ValueError("County source must contain all 21 Swedish counties.")
        if (
            counties.geometry.isna().any()
            or counties.geometry.is_empty.any()
            or not counties.geometry.is_valid.all()
        ):
            raise ValueError("County source contains missing, empty or invalid geometry.")
        counties["_climate_zone"] = counties["_county_code"].map(_ZONE_CODES)
        zones = counties.dissolve(by="_climate_zone")
        if tolerance:
            zones.geometry = zones.geometry.simplify(tolerance, preserve_topology=True)
        if not zones.geometry.is_valid.all():
            raise ValueError("Dissolved climate-zone geometry is invalid.")
        scb = urllib.parse.urlparse(url).hostname in {"www.scb.se", "scb.se"}
        source_metadata = {
            "url": url,
            "sha256": source_hash,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "layer": layer,
            "archive_member": archive_member,
            "source_crs": source_crs,
            "provider": "Statistics Sweden (SCB)" if scb else "Lantmäteriet",
            "description": "Digitala gränser, county Shapefile"
            if scb
            else "Kommun, län och rike, county layer",
        }
        if scb:
            source_metadata.update(
                {
                    "metadata_url": SCB_METADATA_URL,
                    "license": "CC0",
                    "generalised": True,
                    "accuracy_note": "SCB describes these as simple boundaries for thematic statistics, not suitable for precise analyses. The 100 m project guard is not a guarantee of source accuracy.",
                }
            )
        document = {
            "schema_version": 1,
            "crs": "EPSG:3006",
            "simplify_tolerance_m": tolerance,
            "boundary_tolerance_m": max(tolerance, guard),
            "purpose": "Historical three-zone catalogue screening, not current regulation or survey-precise boundary classification",
            "source": source_metadata,
            "county_to_zone": _ZONE_CODES,
            "zones": [
                {"id": zone, "geometry": row.geometry.__geo_interface__}
                for zone, row in zones.sort_index().iterrows()
            ],
        }
        output = Path(output_path)
        raw = json.dumps(
            document, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(gzip.compress(raw, mtime=0) if output.name.endswith(".gz") else raw)
        _load_boundaries.cache_clear()
        return output
