# Shared construction composition

The bundled catalogue and custom authoring use the same physical classes. Loading
resolves canonical references in this order:

`Material → Layer → Component → Element / Window → ConstructionSet → Archetype`

A material combines Honeybee thermal properties with a Boverket product reference
and resolved carbon values where applicable. Layers retain thicknesses and area
fractions. Components retain layer ordering and shearing-layer assignments.
Elements retain their physical components and building role. Construction sets
assign elements to roles; archetypes select construction sets.

```python
from epsm_data import Catalogue

catalogue = Catalogue.load()
slot = catalogue.get_slot("multi_family:SE.02:SE.Zone3:existing")
archetype = catalogue.get(slot.archetype_id, state=slot.state)
assert archetype.construction_set is catalogue.construction_sets[slot.construction_set_id]
```

Equivalent physical definitions share one canonical ID. Their identity does not
depend on which archetype uses them. Aliases may retain familiar names, while
references point to the canonical record. The loaded graph is immutable.

The catalogue contains accepted physical compositions. It does not reconstruct
layers from U-values or assess agreement with independent targets. U-values and
other forward properties are calculated from the stored composition.

Missing values remain visible through `Catalogue.completeness()`. Physically
incomplete leaves are not replaced by synthetic defaults; valid parts remain
inspectable. Custom authoring can likewise start with a partial `Archetype` and
add known definitions. See [authoring](archetype-authoring.md).

Canonical database corrections are ordinary JSON changes reviewed through a PR.
Review all referencing constructions when changing a shared definition. There is
no runtime revision tree or evidence-acceptance workflow.
