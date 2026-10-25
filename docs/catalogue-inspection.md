# Catalogue selection and inspection

`Catalogue.load()` captures the bundled definitions for offline selection and
inspection. `Catalogue.load(path)` accepts a normalized catalogue JSON file or a
directory containing `catalogue.json`.

```python
from epsm_data import Catalogue

catalogue = Catalogue.load()
print(catalogue.summary())
archetype = catalogue.for_year("multi_family", 1970, state="existing")
print(catalogue.completeness("mf_se02", state="existing"))
```

There are 28 families, 76 physical configurations and 228 climate assignments.
Categories are `single_family`, `multi_family`, `office` and `school`.
SE.01–SE.06 offer `existing`, `standard` and `advanced`; an omitted state selects
`existing`. SE.07 starts in 2022 and uses `state=None`.

| Interface | Result |
| --- | --- |
| `ids(category=None)` | Authored family IDs |
| `get(id, state=None)` | An `Archetype` |
| `for_year(category, year, state=None)` | Selection by construction era |
| `renovation_states(id)` | Available states; empty for SE.07 |
| `search(category=None, era=None, climate_zone=None, state=None)` | Assignment slots |
| `get_slot(key)` | Assignment selected by `ArchetypeKey` or four-part string |
| `completeness(id, state=None)` | Completeness and explicit missing-value paths |
| `to_dict()` | Detached canonical references and recipes |
| `resolved_dict()` | Explicit resolved property/source snapshot |
| `sanity_report(fixture=None)` | Forward checks and readiness by input domain |

```python
from epsm_data import ArchetypeKey

key = ArchetypeKey("multi_family", "SE.02", "SE.Zone3", "existing")
slot = catalogue.get_slot(key)
assert slot.key.id == "multi_family:SE.02:SE.Zone3:existing"
assert slot.archetype_id == "mf_se02"
```

Climate assignments reuse the same physical compositions.
[Offline location lookup](climate-zones.md) can select the zone.

## Generic selection

For an unknown building type, explicitly select `generic` to borrow the matching
MF era, state and residential profile:

```python
generic = catalogue.for_year("generic", 1970, state="standard")
donor = catalogue.get("mf_se02", state="standard")
assert generic.construction_set is donor.construction_set
assert generic.display_name == "Unknown building type — multifamily assumption"
```

The seven virtual generic families add no physical records. `get("generic_se02")`
and the inspection methods accept their virtual IDs. `search(category="generic")`
returns 57 assignments; `ids(category="generic")` lists the MF donor IDs. Generic
slots preserve the requested category and identify the donor in `selection`.
Saved archetypes and nominal exports retain this assumption.

## Reusable definitions and checks

`materials`, `windows`, `layers`, `components`, `elements` and `construction_sets`
are read-only mappings of canonical IDs to shared objects. `material_mappings`
exposes the canonical reference-only mappings; `material_records` exposes the
resolved material properties and links. `honeybee_materials` (EnergyPlus-format thermal
records, named for the export format), `boverket_resources` and
`carbon_references` expose the records linked by the catalogue. Full original
datasets remain available through `SourceCache.records(source_id)`, including
unused resources. Source identifiers and fields retain their original values.

`to_dict()` saves the canonical references and recipes; `resolved_dict()` expands
the verified source/property snapshot for explicit auditing or custom inputs.
See [source cache](source-cache.md) for pinned releases and version checks.

Completeness identifies missing physical and source inputs. Sanity checks add
forward calculations, source comparisons and affected assignments, with thermal,
carbon, operating and reference coverage reported separately. Unknown inputs
remain `None`; zero means a known zero. Invalid physics and dangling references
are rejected during loading. See [sanity checks](catalogue-sanity.md) for report
semantics and the command-line checks.

## Save and export

```python
from epsm_data import archetype_to_dict, export_nominal_constructions

saved = archetype_to_dict(archetype)
bundle = export_nominal_constructions(
    archetype, metadata=catalogue.nominal_metadata("mf_se02", state="existing")
)
```

The archetype exchange retains complete physical inputs. The nominal bundle
calculates construction properties forward for consumption by Core and other
adapters. Geometry, soil and simulation scenarios are supplied at application;
see [building application](building-application.md).
