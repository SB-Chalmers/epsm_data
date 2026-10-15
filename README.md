# EPSM Data

EPSM's current construction catalogue, physical construction types, sourced operating inputs and renovation definitions. The package is usable without Core, a database, network access or a simulation engine. Importing it does not load a catalogue.

## Start here

```sh
python -m pip install -e '.[dev]'
```

```python
from epsm_data import Catalogue

catalogue = Catalogue.load()
archetype = catalogue.for_year("multi_family", 1970)
construction = archetype.construction_set

modern = catalogue.for_year("multi_family", 2022)
assert catalogue.renovation_states("mf_se07") == ()
```

The physical hierarchy is **Material → Layer → Component → Element → ConstructionSet**. `Archetype` adds identity and classification to a ConstructionSet. Core uses these same classes when assigning constructions to actual building geometry.

- `LayerMaterial` records a material's parallel area fraction and thickness.
- Unequal constituent depths remain available for quantities and portable exchange;
  `Layer.r_value` rejects them until an explicit thermal representation is supplied.
- `LayerSlot.position` orders layers outside to inside within a Component.
- `Element.components` is an explicit outside-to-inside tuple.
- Geometry, actual element area, material occurrences and ordered building stages belong to Core.
- `Material` and `Archetype` are public names for the existing `OpaqueMaterial` and `BuildingArchetype` types; there is no second physical hierarchy.

## One current catalogue

SE.01–SE.06 retain their existing, standard and advanced reference constructions. **SE.06 covers 2006–2021. SE.07 covers 2022 onward and has one configuration, with no renovation states.** SE.07 independently copies the current SE.06 Advanced physical values, complete construction recipes and material definitions. Its source references remain explicit; the copy is an assumption for the new period, not new measurement evidence.

The current matrix has 35 canonical archetypes, 95 configurations and 1,140 classification slots across five categories, three climate zones and four ventilation classifications. Two additional source variants remain available. Each canonical configuration provides seven construction roles; the actual building determines which are present. Climate and ventilation classifications do not alter the fabric recipe.

The packaged property catalogue contains final resolved values. Updating one property does not propagate through an anchor or override chain:

```python
properties = catalogue.parametric.with_property(
    "multi_family", "SE.06", "advanced", "external_wall",
    {"value": 0.2, "source": "proxy", "note": "Illustrative explicit edit"},
)
```

Edits return a new validated object and mark affected evidence for review. Save the returned data explicitly if it should become the current catalogue. Paired construction recipes must remain consistent with the selected property. The old schema-1 reader is retained for caller-supplied files; bundled runtime inputs use schema 2.

## Author, edit and exchange constructions

```python
import json
from epsm_data import (
    BuildingElement, construction_set_to_dict, construction_set_from_dict,
    reference_construction_set,
)

construction = reference_construction_set()  # explicit illustrative preset
wall = construction.elements[BuildingElement.EXT_WALL]
edited_wall = wall.with_changes(name="Project wall")
edited = construction.with_element(BuildingElement.EXT_WALL, edited_wall)
restored = construction_set_from_dict(json.loads(json.dumps(construction_set_to_dict(edited))))
assert restored == edited
```

Shared graph objects are immutable. `with_changes` validates replacements; construction mappings cannot be modified in place. Material carbon information is optional and unknown remains `None`. `EnvironmentalFactor` records a sourced impact per explicit kg, m², m³, item or kWh basis. LCA applies those factors to actual quantities and the chosen assessment timing.

See [examples/archetype.py](examples/archetype.py) and [examples/renovations.py](examples/renovations.py).

Reusable Sveby profiles, explicit BEN DHW selections and custom portable inputs
are described in [Operating profiles](docs/operating-profiles.md). Start offline
with [the profile notebook](examples/01_operating_profiles.ipynb).

Author complete or partial definitions with the shared `Archetype` class. See
[Archetype authoring and format-4 exchange](docs/archetype-authoring.md) and
[the materials-to-archetype notebook](examples/02_author_archetype.ipynb).

## Renovation and operating inputs

`RenovationCatalogue` contains `RenovationMeasure` definitions. A resolved measure can contain `ConstructionOperation` actions to add, replace or remove components, or replace an element. `SystemOperation` describes an HVAC replacement using `HVACTemplate`. Core applies these actions to selected physical building elements, records material and equipment changes, and builds ordered stages. Assessment dates are a separate LCA setting.

`OperatingProfile` and `HVACTemplate` are immutable, serializable definitions containing Core-neutral values and source references. `load_operating_profile` loads the retained Sveby, BEN DHW or explicit generic fallback inputs. Core keeps calendar expansion, schedule mathematics and factories that construct physics specifications. The four sourced JSON records and generic fallback constants previously held in Core now live in `datasets/standards`.

## Integration and evidence

EPSM owns catalogue-to-building adapters. Use `epsm.catalogue_application.resolve_building_archetype` or the platform's Building API. Old Data application, release and native-validation entry points forward explicit calls to EPSM. None is required to use Data itself. The former cohort-inference forwarding module is [archived](docs/archive/README.md) with the retired study-specific code; it is no longer an active import route.

MF infiltration uses the recorded area/reference-volume convention; see [airflow definitions](docs/airflow-review-notes.md). Effective ground reference properties and nominal layered U-values are distinct. Current source limitations remain attached to records.

Completed study results, prior catalogue snapshots, frozen acceptance manifests, cohort experiment outputs and the historical recalibration search were transferred with SHA-256 verification to `epsm_studies/imports/epsm_data_harmonisation`. Data retains the current source records and assumptions. New studies should save their actual used inputs with their results in Studies.

## Inspect and verify

```sh
python -m explorer.server
python -m epsm_data.parametric --check --summary
python -m epsm_data.layered --check
python -m pytest -q
```

The [local explorer](explorer/README.md) shows properties, complete constructions and source notes. Optional section drawings require `.[visualization]`. Optional integration tests require EPSM, Core and their engine dependencies.

| Location | Responsibility |
| --- | --- |
| `src/epsm_data/domain` | Shared lightweight physical types |
| `src/epsm_data/datasets` | Current catalogue, recipes and sourced input records |
| `src/epsm_data/catalogue.py` | Catalogue access and renovation definitions |
| `src/epsm_data/operations.py` | Declarative physical changes |
| `src/epsm_data/profiles.py` | Operating and HVAC template definitions |
| `evidence` | Retained current source notes and source index |
| `tests`, `examples` | Current contracts and runnable examples |

See [ownership and compatibility](docs/building-application.md) for remaining adapter boundaries.
