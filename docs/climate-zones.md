# Climate-zone lookup

The catalogue uses the three Swedish climate zones of BBR 19. This lookup maps a
location to `SE.Zone1`, `SE.Zone2` or `SE.Zone3` offline, using bundled county
boundaries. The code is in `epsm_data/climate_zones.py`.

Coordinates are **EPSG:3006 (SWEREF 99 TM), in metres, as (easting, northing)**.

```python
from epsm_data import climate_zone_for_county, climate_zone_for_point

assert climate_zone_for_point(674571.866, 6580743.008) == "SE.Zone3"
assert climate_zone_for_county("25") == "SE.Zone1"
assert climate_zone_for_county("Värmlands län") == "SE.Zone2"
```

`climate_zone_for_building(geometry)` accepts a GeoJSON Point, Polygon or
MultiPolygon in EPSG:3006, or any object with `__geo_interface__`. Lookup needs
no optional packages and no network.

## Zones

| Zone | Counties |
| --- | --- |
| `SE.Zone1` | Norrbotten, Västerbotten, Jämtland |
| `SE.Zone2` | Västernorrland, Gävleborg, Dalarna, Värmland |
| `SE.Zone3` | All other counties |

This follows the [BBR 19 three-zone classification](https://rinfo.boverket.se/BFS2011-6/pdf/BFS2011-26.pdf).
An unknown county name or code raises an error. A location outside Sweden
returns `None`.

## Boundaries and accuracy

The boundaries are the [SCB county map of 25 February 2026](https://www.scb.se/contentassets/3443fea3fa6640f7a57ea15d9a372d33/shape_svenska_260225.zip),
21 counties, CC0. SCB simplifies them for statistics, so a **100 m guard**
raises `AmbiguousClimateZoneError` near a zone or national border and for a
footprint that crosses one. The guard flags uncertain cases; it does not make
the boundaries more accurate than [their source](https://www.scb.se/hitta-statistik/regional-statistik-och-kartor/regionala-indelningar/digitala-granser/).

## Rebuild the boundaries

Rebuilding needs the optional `geography` extra (`pip install -e '.[geography]'`):

```python
from epsm_data import build_climate_zone_boundaries

path = build_climate_zone_boundaries("climate_zones.json.gz")
```

Pass `source_path` for a downloaded SCB ZIP, a county Shapefile or a GeoPackage
county layer. The builder requires all 21 counties, reprojects to EPSG:3006 and
records the source URL, SHA-256, retrieval date, file or layer, CRS and county
mapping. For a local file, also pass its real `url`.

For the more precise Lantmäteriet boundaries, where you have access, pass
`url=LANTMATERIET_SOURCE_URL` (from `epsm_data.climate_zones`) and a local
`source_path`. `simplify_tolerance_m` and
`boundary_tolerance_m` change the simplification and the guard; a zero guard
still keeps a 1 mm numerical tolerance.

Test cases for cities, counties and boundary edges are in
`tests/fixtures/climate_zones/`. The tests read another prepared snapshot when
the `EPSM_CLIMATE_ZONE_BOUNDARIES` environment variable points to one.
