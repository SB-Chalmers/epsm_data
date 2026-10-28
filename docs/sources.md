# Material and carbon sources

Every catalogue material points to a thermal record and, where one exists, an
embodied-carbon record. These records are kept in a pinned local copy, the
**source cache**, in `src/epsm_data/datasets/sources/`. Loading and checking it
needs no network. The code is in `epsm_data/sources/cache.py` and
`epsm_data/sources/records.py`.

## What is cached

| Namespace | Pinned release | Contents |
| --- | --- | --- |
| `boverket` | 02.07.000 | Boverket's climate database: the full response, 230 resources and metadata |
| `epsm-custom` | 0.9.0 | 57 EPSM-authored thermal records |
| `epd-ies-0005222`, `epd-ies-0013025` | 003 | Two declared external carbon records (EPDs) |

`manifest.json` records each source's kind, release, file path, format and
SHA-256 checksum. The catalogue's `source_versions` pins each namespace to one
release. Upstream files are kept complete and unchanged, including records the
catalogue does not use.

## Thermal records

Every material uses one of the 57 `epsm-custom` thermal records. Each record
states where its values come from in `user_data.provenance`:

```json
{"tier": "product", "basis": "Matches PAROC eXtra batt.",
 "sources": [{"reference": "EPD NEPD-4340-3565-EN", "url": "https://paroc.com/...",
              "values": {"conductivity": 0.036, "density": 29.5}}]}
```

The tier says what kind of source it is, in order of preference:

| Tier | Source |
| --- | --- |
| `product` | A declared Swedish product (EPD or manufacturer declaration) |
| `tabula` | A TABULA measure |
| `derived` | A documented derivation, such as whole-window optics from glazing values |
| `standard` | A design table (Träguiden, Isolerguiden, Sandin, BR 443) |
| `historical` | Period evidence |
| `assumption` | An assumption; always shown as a review in the [sanity report](sanity.md) |

`evidence/swedish_product_inventory.json` lists the reviewed Swedish products.
Window optics come from the glazing g-value and light transmittance with a frame
fraction of 0.30. Records use the EnergyPlus field layout (`EnergyMaterial`,
`EnergyWindowMaterialSimpleGlazSys`) so they can be exported to EnergyPlus-based
tools.

## Carbon records

Materials link to a Boverket resource or to an external EPD record through
`carbon_ref`. External factors keep their source, method, declared unit and any
proxy description, converted to a per-unit material basis. For example, 2 kg
CO₂e per 1000 kg of product becomes 0.002 kg/kg.

- An unknown factor is `None`; zero is a known zero.
- Undeclared life-cycle modules stay `null`. A5.1 (installation waste) is only
  part of A5.
- The retained sand fill uses the Tagene rock-fines EPD as a proxy: its A1–A3
  production factor is known, while A4 and A5 are unknown.

Unchanged historic stock with no suitable factor can declare
`carbon_assessment.status = "retained_existing_unmapped"` with a reason. This
only covers fabric that stays in place; any new installation, removal or
whole-life assessment still needs a real factor. See [sanity](sanity.md#carbon).

To add an external factor: store its declared record as a versioned cache
source, add its checksum to the manifest, and select it with the material's
`carbon_ref`.

## Load and inspect

```python
from epsm_data import Catalogue, SourceCache

cache = SourceCache.load()        # the packaged cache, checksums verified
catalogue = Catalogue.load(source_cache=cache)
print(cache.manifest)
print(cache.identity)             # checksum of the verified manifest
records = cache.records("boverket")
```

`cache.records(source_id)` returns a detached index of one namespace. Boverket is
indexed by its `ResourceId`; other sources by their record identifier.

A project can use its own cache:

```python
cache = SourceCache.load("project-sources/manifest.json")
catalogue = Catalogue.load("project-catalogue.json", source_cache=cache)
```

An unknown reference, a checksum mismatch or a conflicting release pin stops
loading. Loading never downloads files or switches release.

## Check for newer releases

```python
local = catalogue.check_sources()
upstream = catalogue.check_sources(online=True, timeout=3)  # timeout per request, seconds
```

The local check reports each pin as verified, with remote status `not_checked`.
The online check asks Boverket's version page and reports `current`,
`update_available`, `different_release` or `error`. Sources with no upstream
check, the EPSM records and EPDs, report `not_configured`. Checks never change
files.

```sh
epsm-catalogue --check-sources
epsm-catalogue --check-sources --online --timeout 3
epsm-catalogue --source-cache project-sources --check-sources
```

To update a source, review the new records, checksums, release pins and the
affected sanity results together. Layer thicknesses are never adjusted to make a
new source version pass.
