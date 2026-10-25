# What validation means

The catalogue does not try to explain every building. It succeeds when a building
that matches a cohort (type and construction era) can be simulated with that
cohort's three renovation states, and the plausible range they span contains the
building's measured heating.

Validation code and data live in `epsm_studies`; this page defines the contract.

## One building, one year

1. **Inputs from the building:** footprint, height and storeys (geometry), heated
   area (Atemp), building type, construction year, and the measured space heating
   for one year with that year's weather.
2. **Inputs from the catalogue only:** fabric for each state, the archetype's
   ventilation template, the facade window-to-wall ratios, the operating profile
   and infiltration. Nothing is tuned per building.
3. **Simulate three times:** Existing, Standard and Advanced. SE.07 has one state.
4. **Compare:** `r = simulated / measured` annual space heating for each state.

The building is

- **covered** when its measured heating lies between the Advanced and Existing
  results (the catalogue range brackets reality), and
- **matched** when at least one state has `|r − 1| ≤ 0.20`.

## One cohort

Report per type × era, with at least 10 buildings:

| Measure | Meaning | Provisional target |
| --- | --- | --- |
| Coverage rate | Share of buildings covered | ≥ 70 % |
| Match rate | Share of buildings matched | ≥ 50 % |
| Existing-state median `r` | Bias of the original-construction state | Reported, not a target |
| Selected state | Which state matched, per building | Reported, not a target |

Targets are provisional until the first cohorts are run.

## What validation is not

- **Not calibration.** No catalogue parameter is adjusted to fit individual
  buildings. Renovation state, hidden retrofits, airtightness and ventilation
  performance are unknown, which is why three states are compared.
- **Not a ground model check.** Ground heat transfer is computed by `epsm_core` /
  `epsm_rc` from the nominal floor assemblies.
- **Not a gate on individual buildings.** A cohort result changes the catalogue only
  when it fails systematically and a sourced reason explains why (for example a
  TABULA value, a period building rule or a product declaration).

Fabric agreement with TABULA (walls, thermal top, windows within ±20 %) remains
the primary check inside this repository; see [sanity checks](catalogue-sanity.md).

## Reference buildings

Single well-documented buildings, such as the secondary school in
`evidence/fridhemsskolan_2017_school.md` (published measured and simulated energy
use), use the same three-state test as a smoke check before running cohorts.
