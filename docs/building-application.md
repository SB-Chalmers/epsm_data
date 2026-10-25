# Building application

EPSM Data supplies representative Swedish stock definitions and custom physical
recipes. Select an archetype by type, era and state; a real building record or
measured construction is optional.

```python
from epsm_data import Catalogue

catalogue = Catalogue.load()
archetype = catalogue.for_year("multi_family", 1970, state="existing")
```

| Package | Responsibility |
| --- | --- |
| `epsm_data` | Reusable constructions, source mappings, operating profiles and renovation definitions |
| `epsm_core` | Geometry, physical building occurrences, quantities and engine specifications |
| `epsm` | Apply selected definitions and scenario assumptions to a building |
| `epsm_lca` | Assess quantities with declared factors and lifecycle settings |
| `epsm_db` | Stock observations and catalogue assignment links |
| `epsm_studio` | Authoring interface and project persistence |
| `epsm_studies` / `epsm_workflows` | Study inputs, execution and results |

## Match constructions to geometry

A construction set offers reusable roles. Building geometry determines which
interfaces occur. School/Office SE.01 separates the suspended `GROUND_FLOOR`
above an unheated basement from the concrete `BASEMENT_FLOOR` against soil.
The physical bottom uses the soil role, including a selected at-grade model.
Cold attics similarly separate the `TOP_FLOOR` thermal ceiling and `ROOF` shell.
Intermediate floors use bottom-to-top order for the upper floor face, with a
reciprocal ceiling. The [current nonresidential recipe contract](../evidence/nonresidential_current_recipe_contract.md)
records the period choices.

Existing, Standard and Advanced are fabric states. Climate-zone assignments
reuse stored compositions. Ventilation topology and installed systems are
independent scenario choices.

## Complete a simulation scenario

Combine the selected definitions with geometry, weather, ground conditions,
reference area, a calendar and systems. These can be declared representative
study assumptions. Sveby intensities use Atemp; infiltration retains its stated
area or volume basis. See [operating profiles](operating-profiles.md) and
[airflow units](airflow-inputs.md).

Catalogue completeness covers fabric and source inputs. The consuming engine
validates the resulting scenario. Save the resolved constructions, operating
inputs, areas, factors and ground settings with results so later catalogue
changes do not reinterpret a completed run.
