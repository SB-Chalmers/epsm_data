# Construction composition

Catalogue loading resolves shared definitions in this order:

**Material → Layer → Component → Element / Window → ConstructionSet → Archetype**

- Material mappings resolve pinned thermal and carbon source records.
- Layers retain thicknesses and parallel material fractions.
- Components group ordered layers by shearing layer.
- Elements assign a physical assembly to a building role.
- Construction sets map roles to elements; archetypes select a construction set.

```python
from epsm_data import Catalogue

catalogue = Catalogue.load()
slot = catalogue.get_slot("multi_family:SE.02:SE.Zone3:existing")
archetype = catalogue.get(slot.archetype_id, state=slot.state)
assert archetype.construction_set is catalogue.construction_sets[slot.construction_set_id]
```

Equivalent physical compositions share canonical IDs. The loaded graph is
immutable, and forward properties such as U-values come from the stored layers.
Catalogue maintenance edits the canonical JSON through a pull request; changes to
a shared definition need review across all referencing constructions.

The canonical schema stores `source_versions` and reference-only material mappings:
`epsm_material_name`, `kind`, `thermal_ref`, `carbon_ref` and interpretation metadata.
Each source reference identifies a source namespace and a record identifier. Layers
continue to own dimensions and parallel fractions. The pinned local source cache
owns thermal constants and published carbon records. Canonical mappings do not
repeat these values. Upstream files are cached complete and unchanged; local
thermal exceptions are stored separately in `epsm-custom`.

```python
reference = catalogue.to_dict()       # schema 2: canonical mappings and recipes
resolved = catalogue.resolved_dict()  # schema 1: explicit source/property snapshot
assert reference["source_versions"] == catalogue.source_versions
assert catalogue.material_mappings   # reference-only records
assert catalogue.material_records    # resolved material inspection
```

Use the reference form to save catalogue definitions. Use the resolved form when
an audit or an explicit custom input needs expanded properties and source records.
`Catalogue(...)` accepts either explicit form; resolving references verifies the
selected cache and its pinned releases. See [source cache](source-cache.md).

## Physical order and boundaries

Opaque elements use outside-to-inside order. At an internal horizontal floor,
this is bottom-to-top for the upper room's floor; its reciprocal ceiling reverses
the sequence. Boundary metadata identifies the intended physical role.

A cold attic has a `TOP_FLOOR` thermal ceiling and a separate `ROOF` weather shell.
Early school/office sets offer a suspended `GROUND_FLOOR` above an unheated
basement and a concrete `BASEMENT_FLOOR` at soil. Geometry selects the installed
interfaces. See [building application](building-application.md).

Nominal slab and buried-wall U-values describe their material stacks. Ground
heat transfer additionally uses geometry, soil and a chosen boundary method.
Ground-effective reference values stay separate from material properties.

## Thermal and carbon sources

Materials select thermal records from pinned original Honeybee files or the custom source
namespace, plus a Boverket resource or an external carbon reference where applicable.
The `epsm_material_name` is the catalogue's display name; source display names and
identifiers remain attached to the cached records. A non-product air layer can
declare its exemption.
An exact Honeybee property match uses the original identifier. Unmatched and
modified grades retain their existing thermal properties as custom records;
source-based TABULA and representative historic grades are included in this group.
Layer dimensions remain separate from any source material's example thickness.
External factors retain their source, method, declared unit and proxy description,
normalized per material unit. Unknown factors remain `None`; zero is a known zero.
A5.1 covers a subset of A5.

To add an external factor, capture its declared record in a versioned cache source,
record the file checksum in the manifest, and select it through the material's
`carbon_ref`. For example, a factor of 2 kg CO₂e per 1000 kg product becomes
0.002 kg/kg. Retain undeclared modules as JSON `null`, with source and module
boundaries in the reference.
The catalogue's Tagene rock-fines reference demonstrates this for retained sand:
A1A3 is known while A4/A5 remain unknown.

Unchanged historic stock without a suitable factor can declare
`carbon_assessment.status = "retained_existing_unmapped"` and a reason. Checks
verify unchanged baseline component references. Factors for new installation,
removal and baseline-inclusive LCA still need their own source. See
[sanity checks](catalogue-sanity.md).
