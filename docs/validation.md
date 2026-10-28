# What validation means

The catalogue does not try to explain every building. It succeeds when a building
that matches a cohort (type and construction era) can be simulated with that
cohort's three renovation states, and the plausible range they span contains the
building's measured heating.

Validation code and data live in `epsm_studies` (`validation/catalogue/`); this page
defines the contract.

## One building, one year

1. **Inputs from the building:** footprint, height and storeys (geometry), heated
   area (Atemp), building type, construction year, heating carrier, and the measured
   space heating for one year with that year's weather.
2. **Inputs from the catalogue only:** fabric for each state, the ventilation
   template for the building's EPC ventilation type (era default if unknown), the
   facade window-to-wall ratios, the operating profile and infiltration. Nothing is
   tuned per building.
3. **Simulate three times:** Existing, Standard and Advanced. SE.07 has one state.
4. **Compare like with like:** `r = modelled / measured` delivered heating for each
   state, where *modelled* is the simulated space heating plus the accounting terms
   below, divided by the heating system's efficiency or seasonal COP.

**Accounting terms.** An EPC's measured heating includes energy the building model
does not simulate. These terms describe the measurement, not the building, so they
belong to the comparison and never to the catalogue:

| Term | Value | Source | Applied to |
| --- | --- | --- | --- |
| Window airing | 4 kWh/m² Atemp per year × the municipality's Fgeo | Sveby *Brukarindata bostadshus* 2.0, ch. 5; BFS 2026:9 | multifamily |
| Hot-water circulation losses | BEN normal hot water × (1/0.75 − 1), no internal gain | BEN (BFS 2016:12), 3 § | multifamily |

A term is applied to a building type only when its source defines it for that type
and the cohort test below accepts it. Single-family airing and office circulation
were tested and not accepted.

The building is

- **covered** when its measured heating lies between the Advanced and Existing
  results (the catalogue range brackets reality), and
- **matched** when at least one state has `|r − 1| ≤ 0.20`.

## One cohort

Report per type × era, with at least 10 buildings and preferably 20. Each end of the
range is tested on its own, so a failure names the state that needs work:

| Measure | Meaning | Target |
| --- | --- | --- |
| Above Existing | Share measured above the Existing state | ≤ 15 % |
| Below Advanced | Share measured below the Advanced state (SE.01–SE.06) | ≤ 15 % |
| Match rate | Share of buildings matched | ≥ 50 % |
| Coverage rate | Share of buildings covered | Reported (the two tolerances imply ≥ 70 %) |
| Existing-state median `r` | Bias of the original-construction state | Reported |
| Selected state | Which state matched, per building | Reported |

SE.07 has a single state, so it is judged on match and on its stock placement.

**Stock placement.** Against every eligible measured EPC in the cohort (district
heating, where delivered heat is measured directly), Existing should sit near the
85th percentile of heating per m² Atemp and Advanced near the 15th. Advanced is a
deep-renovation scenario and may sit below the 15th percentile; that is reported,
not corrected.

## Changing the catalogue

A cohort result changes the catalogue only when it fails systematically and a
sourced reason explains why (for example a TABULA value, a period building rule, a
measured stock survey or a product declaration). A change is accepted only if, on
both a calibration sample and a disjoint, seeded hold-out sample:

- the summed shortfall against the three cohort targets falls for the building type;
- the share above Existing does not rise and the match rate does not fall;
- no cohort gets materially worse (its shortfall rising by more than two buildings in
  twenty);
- the value stays inside its sourced range, and is applied per building type or as a
  sourced era trend, never per cohort.

Fabric (U-values, constructions, glazing) is not fitted to measured heating: annual
heating cannot separate transmission from infiltration, recovery, setpoint and
unmodelled losses, and a fitted U-value would overstate renovation savings.

## What validation is not

- **Not calibration.** No catalogue parameter is adjusted to fit individual
  buildings. Renovation state, hidden retrofits, airtightness and ventilation
  performance are unknown, which is why three states are compared.
- **Not a ground model check.** Ground heat transfer is computed by `epsm_core` /
  `epsm_rc` from the nominal floor assemblies.
- **Not a gate on individual buildings.**

Fabric agreement with TABULA (walls, thermal top, windows within ±20 %) remains
the primary check inside this repository; see [sanity checks](catalogue-sanity.md).

## Reference buildings

A single well-documented building, with known geometry and a measured annual (or
full heating-season) space-heating value, should pass the same three-state test as
a smoke check before cohorts are run. No such building is available yet: the
secondary school in `evidence/fridhemsskolan_2017_school.md` has one district-heating
meter for nine buildings including hot water, and its geometry gives areas only.
