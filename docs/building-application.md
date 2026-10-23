# Platform ownership and building application

EPSM Data owns reusable physical definitions, source-property mappings and the
curated LoD2 catalogue. It does not hold building geometry or execute scenarios.

| Repository | Responsibility |
| --- | --- |
| `epsm_data` | Materials, layers, components, elements, windows, construction sets, archetypes and reusable operating/renovation definitions |
| `epsm_core` | Geometry, physical building occurrences, quantities and engine-ready specifications |
| `epsm` | Apply chosen Data definitions to a building and record the explicit choices |
| `epsm_lca` | Assess quantities using factors, units and assessment settings |
| `epsm_db` | Building-stock observations and catalogue assignment links |
| `epsm_studio` | Authoring interface, project persistence and contribution/review actions |
| `epsm_workflows` / `epsm_studies` | Run investigations and retain their actual inputs and results |

```python
from epsm_data import Catalogue

catalogue = Catalogue.load()
archetype = catalogue.for_year("multi_family", 1970, state="existing")
report = catalogue.completeness("mf_se02", state="existing")
```

The result uses the same immutable hierarchy as a custom authored definition.
Its construction set offers available roles. Actual building geometry determines
whether a basement, intermediate floor or other role is present.

Existing, Standard and Advanced are reference fabric alternatives for the first
six eras. SE.07 starts in 2022 and has a single configuration. Climate-zone
classification does not alter a stored composition. Installed systems, ventilation
topology and operating inputs are explicit independent choices.

Data completeness reports missing fabric and mapping values. It does not certify
simulation readiness. Core and EPSM must still supply geometry, site/ground
conditions, compatible reference areas, schedules and systems. Infiltration rates
retain an explicit area or volume basis; see [airflow inputs](airflow-review-notes.md).

Studio should use Data's authoring types, validation and reference semantics.
Private edits become project definitions; shared catalogue corrections are PRs
against canonical JSON. Data does not maintain an internal evidence/revision tree.

Preserve actual resolved material, construction, operating and carbon inputs with
saved runs. A later catalogue PR does not reinterpret an already completed study.
