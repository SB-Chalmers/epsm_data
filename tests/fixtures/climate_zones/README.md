# Climate-zone fixtures

- `synthetic_boundaries.json`: independently authored rectangles, a hole and a disconnected island. Coordinates are offset into the EPSG:3006 range solely to exercise lookup and footprint logic. These polygons do **not** represent Sweden.
- `known_points.json`: manually selected approximate city centres in Stockholm, Gothenburg, Malmö, Umeå, Luleå, Östersund, Sundsvall, Gävle, Falun, Karlstad and Visby, plus Oslo outside Sweden. Original WGS84 positions and the one-time EPSG:3006 transformation are recorded. Expected zones come from county membership independently of the polygons under test.
- `scb_source.json`: expected source ZIP URL, checksum, byte count, selected nested county member, fields, CRS, county/vertex counts, licensing and accuracy limitation. The runtime polygon snapshot is packaged once under `epsm_data.datasets.climate_zones`; it is not duplicated in this test fixture.

Geographic tests run against the bundled SCB snapshot by default. `EPSM_CLIMATE_ZONE_BOUNDARIES` can select a separately prepared dataset. Expected city assignments are not regenerated from the implementation or current catalogue.

SCB's source is generalised for thematic statistics and is not suitable for precise analysis. No extra simplification is applied. A 100 m project boundary guard flags ambiguous points/footprints and does not guarantee source accuracy. https://www.scb.se/hitta-statistik/regional-statistik-och-kartor/regionala-indelningar/digitala-granser/

The county mapping follows historical BBR 19 section 9:12, printed pages 138–139: https://rinfo.boverket.se/BFS2011-6/pdf/BFS2011-26.pdf. This is the historical three-zone catalogue classification, not current building regulation compliance.
