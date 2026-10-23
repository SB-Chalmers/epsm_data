# Inspect the LoD2 catalogue

`Catalogue.load()` reads the bundled normalized catalogue once. Selection and
inspection then use the captured definitions without network or database access.

```python
from epsm_data import Catalogue

catalogue = Catalogue.load()
print(catalogue.summary())
print(catalogue.ids(category="multi_family"))
archetype = catalogue.for_year("multi_family", 1970, state="existing")
report = catalogue.completeness("mf_se02", state="existing")
```

There are 28 families, 76 physical configurations and 228 climate-zone assignments.
The categories are `single_family`, `multi_family`, `office` and `school`.
SE.01–SE.06 each have `existing`, `standard` and `advanced` configurations.
SE.07 starts in 2022 and has one configuration, selected with `state=None`.
For earlier eras an omitted state selects `existing`.

| Interface | Result |
| --- | --- |
| `ids(category=None)` | Family IDs |
| `get(id, state=None)` | Standard authored `Archetype` |
| `for_year(category, year, state=None)` | Archetype selected by construction era |
| `renovation_states(id)` | Available renovation alternatives; empty for SE.07 |
| `search(category=None, era=None, climate_zone=None, state=None)` | LoD2 assignment slots |
| `get_slot(key)` | A slot selected by key object or four-part ID |
| `completeness(id, state=None)` | `complete` and explicit `missing_values` paths |
| `to_dict()` | Detached normalized catalogue for explicit editing or saving |

```python
from epsm_data import ArchetypeKey

key = ArchetypeKey("multi_family", "SE.02", "SE.Zone3", "existing")
slot = catalogue.get_slot(key)
assert slot.key.id == "multi_family:SE.02:SE.Zone3:existing"
assert slot.archetype_id == "mf_se02"
assert slot.complete == report["complete"]
```

Climate zones classify constructions; they do not generate separate copies of the
physical definitions. Ventilation topology is an independent building input.

## Reusable indexes

`materials`, `windows`, `layers`, `components`, `elements` and `construction_sets`
are read-only mappings keyed by canonical IDs. Their children share references.
`material_records` retains every raw material entry, including entries whose
missing thermal properties prevent construction of a validated domain object.
`honeybee_materials` and `boverket_resources` expose the linked source records.

Completeness concerns LoD2 fabric, its thermal inputs, required roles and external
mappings. It does not require geometry, HVAC or operating schedules. A missing
product carbon mapping is flagged; an explicitly declared non-product air layer
needs no Boverket product. Unknown stays `None`, distinct from a known zero.
Invalid supplied physical values and dangling references fail loading.

## Export

```python
from epsm_data import archetype_to_dict, export_nominal_constructions

saved = archetype_to_dict(archetype)
bundle = export_nominal_constructions(
    archetype, metadata=catalogue.nominal_metadata("mf_se02", state="existing")
)
```

The complete archetype exchange retains actual inputs. Nominal construction
export calculates forward from those inputs. Site ground conditions, building
geometry and engine readiness remain downstream responsibilities.
