# Pinned source cache

Catalogue recipes select thermal and carbon records by source namespace and
identifier. `source_versions` pins each namespace to a release. The bundled
`epsm_data.datasets.sources/manifest.json` records each source's kind, release,
file path, format and SHA-256 checksum. Loading verifies the local files, record
identities and declared versions without network access.

The cache keeps the full original Boverket and EPD files, including unused
records and source metadata. Thermal properties are EPSM-authored records; no
external simulation library is bundled or required.

| Source namespace | Pinned release | Captured file |
| --- | --- | --- |
| `boverket` | 02.07.000 | Full database response, 230 resources and metadata |
| `epsm-custom` | 0.9.0 | 57 thermal records with structured provenance |
| Two `epd-ies-*` sources | 003 | Declared external carbon records |

Every material selects one of the 57 `epsm-custom` thermal records. The former
Honeybee/ASHRAE grades (timber, plywood, concrete, render, gypsum, brick) were
replaced by Swedish design values (Träguiden, Isolerguiden, Sandin, BR 443) and
product declarations; the Honeybee libraries held no realistic Nordic insulation
or window grades. Each record carries `user_data.provenance`: a tier (`product`,
`tabula`, `derived`, `standard`, `historical` or `assumption`), a basis and named
sources such as an EPD registration number, manufacturer declaration, TABULA
locator or evidence file. See `evidence/swedish_product_inventory.json` for the
reviewed Swedish products. Records keep the EnergyPlus-compatible
`EnergyMaterial` / `EnergyWindowMaterialSimpleGlazSys` field layout, so the
resolved `honeybee` section and nominal Honeybee export remain consumer formats.
The two external EPD factors remain explicit exceptions to Boverket.

These pins capture catalogue inputs. Source attribution and upstream locators
ship with the cached files.

## Load and inspect

```python
from epsm_data import Catalogue, SourceCache

cache = SourceCache.load()  # verified packaged snapshots
catalogue = Catalogue.load(source_cache=cache)
print(cache.manifest)
print(cache.identity)      # checksum of the exact verified manifest bytes
print(catalogue.check_sources())
```

`cache.records(source_id)` returns detached, indexed records from a verified
namespace. Boverket is indexed by its original `ResourceId`; other sources use their
record identifier. Parsing builds the view in memory and leaves raw
source files unchanged.
`cache.manifest` is also detached. Material mappings preserve their EPSM display
name in `epsm_material_name` and select `thermal_ref`/`carbon_ref` records. Cached
source names, constants and carbon modules remain source-owned.

`catalogue.to_dict()` returns the reference-only canonical payload.
`catalogue.resolved_dict()` returns an explicit expanded property/source snapshot
for forward auditing or custom authoring. `material_mappings` exposes reference-only
material records; `material_records` exposes the resolved inspection view. Both
explicit payload forms can be supplied to `Catalogue(...)`.

A caller can select a cache directory or manifest file:

```python
cache = SourceCache.load("project-sources/manifest.json")
catalogue = Catalogue.load("project-catalogue.json", source_cache=cache)
```

Unknown references, checksum mismatches and conflicting pinned releases fail
resolution. A custom cache is explicit project input; loading a catalogue does
not download a replacement or choose a different release.

## Check upstream versions

```python
local = catalogue.check_sources()
upstream = catalogue.check_sources(online=True, timeout=3)
```

The default reports locally verified pins with remote status `not_checked`.
Explicit online checks consult the Boverket version page. They report `current`, `update_available`,
`different_release` or `error` per source. Sources without an upstream probe,
including the authored records and EPD snapshots, report `not_configured`.
The timeout is per request. Checks leave cache files and catalogue mappings intact.

```sh
epsm-catalogue --check-sources
epsm-catalogue --check-sources --online --timeout 3
epsm-catalogue --source-cache project-sources --check-sources
```

Updating a source means reviewing the captured records, checksums, release pins
and affected construction checks together. Sanity checks calculate from the
resolved inputs; physical layer dimensions and nominal properties are never
fitted to make a new source version pass.
