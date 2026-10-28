# The archetype catalogue

The catalogue holds representative Swedish buildings, called archetypes. Each
archetype gives the constructions (walls, roofs, floors, windows) that were
typical for one building type and construction era. It is a stock
representative, not a survey of a real building. An address or a measured
building record is optional.

The code is in `epsm_data/catalogue/catalogue.py`; the data is in
`src/epsm_data/datasets/lod2/catalogue.json`.

## What the catalogue contains

| Dimension | Values |
| --- | --- |
| Building type (`category`) | `single_family`, `multi_family`, `office`, `school` |
| Construction era | SE.01 to SE.07. SE.06 covers 2006–2021; SE.07 starts in 2022. |
| Renovation state | `existing`, `standard`, `advanced` for SE.01–SE.06. SE.07 has one state, selected with `state=None`. |
| Climate zone | `SE.Zone1`, `SE.Zone2`, `SE.Zone3` |

That gives 28 archetype families, 76 physical configurations and 228
climate-zone assignments. The three climate zones reuse the same stored
constructions. Use the [climate-zone lookup](climate-zones.md) to find the zone
for a location.

*Existing* is the original construction. *Standard* and *Advanced* are
renovated fabric states. An omitted state selects `existing`.

## Select an archetype

```python
from epsm_data import ArchetypeKey, BuildingElement, Catalogue

catalogue = Catalogue.load()
archetype = catalogue.for_year("multi_family", 1970, state="existing")
wall = archetype.construction_set.elements[BuildingElement.EXT_WALL]
print(wall.u_value)  # W/(m² K)

key = ArchetypeKey("multi_family", "SE.02", "SE.Zone3", "existing")
slot = catalogue.get_slot(key)
assert slot.key.id == "multi_family:SE.02:SE.Zone3:existing"
assert slot.archetype_id == "mf_se02"
```

`Catalogue.load()` reads the bundled catalogue offline. `Catalogue.load(path)`
reads another catalogue JSON file, or a directory that contains
`catalogue.json`.

| Method | Returns |
| --- | --- |
| `ids(category=None)` | Archetype family IDs, such as `mf_se02` |
| `get(id, state=None, ventilation=None)` | An `Archetype` |
| `for_year(category, year, state=None, ventilation=None)` | The archetype for the era that contains `year` |
| `renovation_states(id)` | Available states; empty for SE.07 |
| `search(category=None, era=None, climate_zone=None, state=None)` | Matching assignments (`ArchetypeSlot`) |
| `get_slot(key)` | One assignment, by `ArchetypeKey` or a four-part string |
| `ventilation_options(id, state=None)` | The ventilation templates the archetype can use |
| `facade_assumptions(id)` | Window-to-wall ratios per orientation |
| `completeness(id, state=None)` | Whether every input is present, with paths to missing values |
| `summary()` | Counts of families, configurations and assignments |
| `sanity_report(fixture=None)` | The [sanity screens](sanity.md) |
| `check_sources(online=False, timeout=3)` | The [source cache](sources.md) check |

`ventilation` selects a ventilation template; see [profiles](profiles.md).

### Unknown building type

For a building of unknown type, select `generic`. It borrows the multi-family
archetype for the same era, state and zone, with the residential operating
profile:

```python
generic = catalogue.for_year("generic", 1970, state="standard")
donor = catalogue.get("mf_se02", state="standard")
assert generic.construction_set is donor.construction_set
assert generic.display_name == "Unknown building type — multifamily assumption"
```

The seven generic families (`generic_se01` … `generic_se07`) add no physical
records. `search(category="generic")` returns 57 assignments, and
`ids(category="generic")` lists the multi-family donor IDs. A generic slot keeps
the requested category and names its donor in `selection`. Saved archetypes and
exports keep this assumption.

## How an archetype is composed

Every archetype, from the catalogue or written by hand, uses the same immutable
hierarchy:

**Material → Layer → Component → Element / Window → ConstructionSet → Archetype**

- A **material** links to a thermal record and, where available, a carbon record.
- A **layer** gives a material its thickness in metres. Parallel materials, such
  as timber studs in insulation, carry area fractions that sum to one.
- A **component** groups ordered layers by shearing layer (`ShearingLayer`:
  Skin, Structure, Services, Space, Stuff), the parts of a building that change
  at different rates.
- An **element** is a complete assembly with a role, such as `EXT_WALL` or `ROOF`.
- A **construction set** maps each role to an element. An **archetype** selects
  a construction set and may add an operating profile, a ventilation template and
  envelope inputs.

Identical compositions share one canonical ID and one object. U-values and other
properties are calculated forward from the stored layers; nothing is fitted to a
target.

```python
slot = catalogue.get_slot("multi_family:SE.02:SE.Zone3:existing")
archetype = catalogue.get(slot.archetype_id, state=slot.state)
assert archetype.construction_set is catalogue.construction_sets[slot.construction_set_id]
```

The shared definitions are read-only mappings from ID to object:
`materials`, `windows`, `layers`, `components`, `elements` and
`construction_sets`. The linked source records are in `thermal_materials`,
`boverket_resources` and `carbon_references`.

### Layer order and boundaries

- Opaque elements list layers from outside to inside.
- An intermediate floor lists layers bottom to top, seen from the room above. Its
  matching ceiling lists them in reverse.
- A cold attic has two roles: `TOP_FLOOR`, the insulated ceiling, and `ROOF`, the
  weather shell.
- Early school and office sets have both a suspended `GROUND_FLOOR` above an
  unheated basement and a concrete `BASEMENT_FLOOR` against soil.

A construction set offers roles; the building's geometry decides which ones
occur. The physical bottom of a building uses the soil role. The
[nonresidential recipe contract](../evidence/nonresidential_current_recipe_contract.md)
records the period choices for schools and offices.

Slab and buried-wall U-values describe only the material stack. Heat loss to the
ground also depends on geometry and soil, and is calculated by `epsm_core` /
`epsm_rc`.

## Saved forms

| Call | Contents |
| --- | --- |
| `catalogue.to_dict()` | Reference form (schema 2): recipes and material mappings that point to source records |
| `catalogue.resolved_dict()` | Resolved form (schema 1): the same, with thermal and carbon values expanded |

Use the reference form to save catalogue definitions. Use the resolved form for
an audit or as an explicit custom input. `Catalogue(...)` accepts either form.

A material mapping holds `epsm_material_name` (the catalogue's display name),
`kind`, `thermal_ref`, `carbon_ref` and interpretation notes. The values
themselves live in the [source cache](sources.md). `material_mappings` returns
the reference form and `material_records` the resolved one.

## Hand the archetype to Core

`export_nominal_constructions` (in `catalogue/handover.py`) calculates the
nominal properties of each construction for `epsm_core` and other adapters.
`validate_nominal_handover` checks a bundle.

```python
from epsm_data import export_nominal_constructions

bundle = export_nominal_constructions(
    archetype, metadata=catalogue.nominal_metadata("mf_se02", state="existing")
)
```

The bundle carries constructions only. Geometry, ground conditions, weather and
the simulation scenario come from the building that uses it; see
[authoring](authoring.md#apply-an-archetype-to-a-building).

The [first example notebook](../examples/01_select_an_archetype.ipynb) walks
through selection and inspection.
