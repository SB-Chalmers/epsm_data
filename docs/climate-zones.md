# Offline climate-zone lookup

The bundled SCB county boundaries map a Swedish location to `SE.Zone1`,
`SE.Zone2` or `SE.Zone3`. Coordinates use **EPSG:3006 (SWEREF 99 TM), metres,
(easting, northing)**.

```python
from epsm_data import climate_zone_for_point, climate_zone_for_county

assert climate_zone_for_point(674571.866, 6580743.008) == "SE.Zone3"
assert climate_zone_for_county("25") == "SE.Zone1"
assert climate_zone_for_county("Värmlands län") == "SE.Zone2"
```

`climate_zone_for_building(geometry)` accepts an EPSG:3006 GeoJSON Point, Polygon
or MultiPolygon, including objects with `__geo_interface__`. Lookup needs no
optional packages or network. Supply valid projected geometry; lookup preserves
its coordinates.

## Classification and boundary cases

Norrbotten, Västerbotten and Jämtland map to Zone 1. Västernorrland, Gävleborg,
Dalarna and Värmland map to Zone 2. Other recognized Swedish counties map to Zone 3.
This follows the catalogue's [BBR 19 three-zone classification](https://rinfo.boverket.se/BFS2011-6/pdf/BFS2011-26.pdf).
Unknown county names/codes raise an error; locations wholly outside the supplied
Swedish polygons return `None`.

The source is the [SCB county distribution dated 25 February 2026](https://www.scb.se/contentassets/3443fea3fa6640f7a57ea15d9a372d33/shape_svenska_260225.zip),
with 21 counties under CC0. SCB generalizes these boundaries for thematic
statistics. A **100 m boundary guard** raises `AmbiguousClimateZoneError` near
zone or national borders and for straddling footprints. Holes, islands and edge
crossings are checked. The guard supports screening, rather than improving the
[source's positional accuracy](https://www.scb.se/hitta-statistik/regional-statistik-och-kartor/regionala-indelningar/digitala-granser/).

## Refresh the snapshot

The optional `geography` extra is needed only for preparation:

```python
from epsm_data import build_climate_zone_boundaries

path = build_climate_zone_boundaries("climate_zones.json.gz")
```

Pass `source_path` for a downloaded SCB ZIP, county Shapefile ZIP, Shapefile or
GeoPackage county layer. The builder records source URL, SHA-256, retrieval date,
file/layer, CRS and mapping. It requires all 21 counties and reprojects to
EPSG:3006. Local sources should retain their actual `url` for provenance.

An authorized higher-precision source can be supplied explicitly with
`url=LANTMATERIET_SOURCE_URL` from `epsm_data.climate_zones` and a local
`source_path`. Access failures are reported. Default preparation adds no further
simplification and retains the 100 m guard. `simplify_tolerance_m` and
`boundary_tolerance_m` are explicit project choices; a zero guard still retains
1 mm numerical tolerance.

Independent city/county expectations and synthetic boundary cases live in
`tests/fixtures/climate_zones/`. `EPSM_CLIMATE_ZONE_BOUNDARIES` selects another
prepared snapshot for the same geographic checks.
