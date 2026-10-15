# Compose the catalogue's physical definitions

The MF SE.02 pilot established physical composition independently of target
assessment. All predefined entries now use the same route; see
[Catalogue inspection and reuse](catalogue-inspection.md). Existing, Standard
and Advanced recipes retain their material properties, layer order, thicknesses,
fractions, U-values and stable identities.

```python
from epsm_data import Catalogue

catalogue = Catalogue.load()
archetype = catalogue.get("mf_se02", state="existing")
assert archetype.construction_set == catalogue.detailed.compose("mf_se02").construction_set
assert archetype.total_elements == 7
assert archetype.source_references
```

`DetailedCatalogue.compose(archetype_id, state=None)` uses an already loaded
registry. Omitted state selects Existing before SE.07; SE.07 accepts only
`state=None`. It constructs the immutable materials, layers, components, elements
and construction set without asking whether a target matches. Invalid physical
values still fail validation. This operation performs no file or network access
and never retunes a material property or thickness.

The returned archetype retains source identities and descriptions in
`source_references`. Its notes retain scope, assumptions and caveat status,
severity and text. `catalogue.detailed.review(id, state)` retains structured
evidence, boundary details and caveat ownership. Targets remain separately
available in the registry and effective-property catalogue. Loading a construction
does not establish calibration, simulation readiness or accuracy for a measured
building.

For an explicit calibration assessment during the staged migration, use
`load_calibrated_archetype(...)` and inspect its `report`; source/material edits
can produce failed tolerance checks or target drift without preventing physical
composition. Supported operating profiles and explicit envelope bases are attached by
`Catalogue.get()`. HVAC remains an explicit choice. `DetailedCatalogue.compose()`
continues to return the physical composition alone.

Run [the offline composition example](../examples/catalogue_composition.py) with
the installed development revision. It writes no files and needs no Core,
database or engine. Complete exchange uses `archetype_to_dict()` format 4.
