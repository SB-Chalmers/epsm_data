# Construction data and building application

## Ownership

Data owns Material, Layer, Component, Element and ConstructionSet. Archetype combines reusable constructions, operating profiles, system templates and explicit envelope assumptions; partial custom definitions may omit sections. The types are lightweight and shared directly with Core.

Core owns actual building geometry, physical element instances, system instances, material quantities and ordered renovation stages. EPSM resolves evidence and catalogue selections into those objects. EPlus and RC consume a resolved stage; LCA consumes quantities, operating consequences and sourced factors; Workflows explores measure combinations and ordering.

## Current catalogue selection

```python
from epsm_data import Catalogue

catalogue = Catalogue.load()
old = catalogue.for_year("multi_family", 1970, state="existing")
modern = catalogue.for_year("multi_family", 2022)
```

SE.06 ends at 2021. SE.07 starts in 2022 and accepts no renovation state. A detailed compatibility view uses a `None` configuration key internally; serialized authoring data uses a single `configuration` field. The parametric slot identifier uses `default` as an identifier token while `ArchetypeKey.renovation_state` remains `None`.

Existing, Standard and Advanced for earlier eras are reference alternatives. A real building's installed fabric should be chosen from independent evidence. A window replacement does not imply a new wall construction or an airtightness change.

## Editing and renovation

Use immutable `with_changes` replacements and lossless `construction_set_to_dict` / `construction_set_from_dict`. Parallel material fractions must sum to one and share layer depth. Layer positions are unique, and component order is the physical outside-to-inside order.

A `ConstructionOperation` targets a construction role and, for component replacement/removal, an exact component name. Addition requires an explicit position. `RenovationMeasure.target_element_ids` optionally limits which actual Core elements receive a measure. System replacement uses `SystemOperation` with an `HVACTemplate`. Data can execute pure fabric changes; Core applies mixed fabric/system measures and records the resulting quantities and equipment.

Stages are ordered. There is no implicit construction or renovation date in a new ConstructionSet. Legacy `valid_from_year`, `RenovationEvent` and archetype renovation-log fields remain readable for old saved callers; new stage execution does not depend on them.

## Source inputs and remaining compatibility

Sourced Sveby residential, office and school records and BEN DHW inputs are packaged in Data. The generic nonresidential fallback is explicitly labelled as an EPSM assumption. `OperatingProfile` and `HVACTemplate` store finite portable values with source references. Core interprets the inputs, expands calendars and constructs schedules and physics specifications.

The older detailed registry and nominal export code retain some review metadata names and source-era identifiers for compatibility. Their source labels are provenance; the shipped runtime catalogue does not load historical versions or apply an override chain. Data application/native-validation forwarders have been removed. Call the public owning EPSM adapters or `Building.apply_archetype`; see [the API migration guide](archetype-api-migration.md). The former cohort-modelling compatibility module is [archived](archive/README.md); reproducing the retired cohort studies is outside current maintenance.

The current source records still contain representative material choices, simple whole-window optics and effective ground assumptions. Source coverage is not proof that a model matches any particular measured building. Comparisons require aligned areas, periods, energy boundaries, weather and operating conditions in the application or study.

## Study outputs

Prior snapshots, frozen validation receipts and completed cohort/calibration results live in `epsm_studies/imports/epsm_data_harmonisation`, with a transfer manifest. Data keeps current values and source information. A completed study preserves the exact inputs it actually used alongside its results; it does not require Data to maintain a second evolving catalogue.
