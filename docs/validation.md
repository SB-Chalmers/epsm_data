# Measured-data validation

The catalogue does not try to explain every building. It succeeds when a building
that matches a cohort (type and construction era) can be simulated with that
cohort's three renovation states, and the plausible range they span contains the
building's measured heating.

This page defines the contract and says briefly how the catalogue was calibrated
against it. Study samples, runs and results are kept outside this package.

## One building, one year

1. **Inputs from the building:** footprint, height and storeys (geometry), heated
   area (Atemp), building type, construction year, heating carrier, and the measured
   space heating for one year with that year's weather.
2. **Inputs from the catalogue only:** fabric for each state, the ventilation
   template for the ventilation type in the building's energy performance
   certificate (EPC; the era default if unknown), the facade window-to-wall
   ratios, the operating profile and infiltration. Nothing is tuned per building.
3. **Simulate three times:** Existing, Standard and Advanced. SE.07 has one state.
4. **Compare like with like:** `r = modelled / measured` delivered heating for each
   state, where *modelled* is the simulated space heating plus the accounting terms
   below, divided by the heating system's efficiency or seasonal COP.

**Accounting terms.** An EPC's measured heating includes energy the building model
does not simulate. These terms describe the measurement, not the building, so they
belong to the comparison and never to the catalogue:

| Term | Value | Source | Applied to |
| --- | --- | --- | --- |
| Window airing | 4 kWh/m² Atemp per year × the municipality's Fgeo (geographic adjustment factor) | Sveby *Brukarindata bostadshus* 2.0, ch. 5; BFS 2026:9 | multifamily |
| Hot-water circulation losses | BEN normal hot water × (1/0.75 − 1), no internal gain | BEN (BFS 2016:12), 3 § | multifamily |

A term is applied to a building type only when its source defines it for that type
and the cohort test below accepts it. Single-family airing and office circulation
were tested and not accepted.
`select_epc_comparison_terms(building_type, municipality_code=...)` gives every
sourced value; the column above records which ones the comparison applies.

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

SE.07 has a single state, which spans no range. It is judged on match, on the share
measured above that state, and on its stock placement; it has no bottom target.

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

## How the catalogue was calibrated

The catalogue was compared with measured EPC heating on two disjoint, seeded samples of
buildings (calibration and hold-out). Only operating and accounting inputs that have a
sourced range were changed, each per building type, and each only when it passed the rule
above on both samples:

- multifamily: measured indoor temperature by era and the measured self-draught air change (BETSI);
- offices: ventilation flow and hours (Sveby kontor operator examples) and the TABULA
  thermal-bridge allowance;
- heat pumps: the Swedish field-average seasonal COP of 2.75;
- EPC comparison terms: window airing and hot-water circulation for multifamily.

Fabric was not fitted. Single-family houses and schools keep Sveby normal use, because no
measured input passed for them. What remains between the catalogue and measured heating is
mostly building-specific (use, renovation history, operation) and cannot be closed by
archetype values. The `measured` operating standard selects these values; Sveby normal use
stays the default.

### Heat-pump COP by pump type

The heat-pump seasonal COP follows the EPC's pump type: ground 2.75, exhaust air 2.4
before 2006 (radiators) and 2.75 from 2006 (floor heating), air–water 2.4, air–air 2.0.
In the pre-registered test of 22 November 2026 it moved matches the expected way but did
not pass the rule (calibration + hold-out 16 gained, 8 lost, p 0.15; third sample 12
gained, 5 lost). A later test on unseen single-family houses supported it: heat-pump
houses rose from 59.7 % to 64.6 % (p < 0.001), mostly exhaust-air pumps in SE.04–SE.05.

SE.07 FTX recovery 0.70 (in-use) instead of 0.80 was also tested twice and did not pass
(the second test: 123 to 122 matches of 481), so SE.07 keeps 0.80.

## School existing state (STIL2)

School SE.01 (to 1960) and SE.02 (1961–1975) use a measured "as found" existing state for
the external wall and the windows. The values are the medians of Energimyndigheten's STIL2
inspections of schools in 2006 (ER 2007:11, Bilaga 4). For each school, the inspectors gave
wall, roof and window U-values with the build year and the envelope measures carried out:

| Era | Schools | Wall U | Window U | Roof U | Original existing |
| --- | ---: | ---: | ---: | ---: | --- |
| SE.01 | 43 | 0.70 (IQR 0.65–0.82) | 2.3 | 0.45 | wall 1.19, window 2.8, roof 0.46 |
| SE.02 | 29 | 0.40 | 1.9 | 0.30 | wall 0.48, window 2.7, roof 0.30 |

- Few of these schools had been renovated: added wall insulation in 3 of the 43 older
  schools, and replaced windows in 6. The original 380 mm brick recipe therefore understates
  real school walls; the difference is not a renovation.
- The roof agrees with STIL2 and is unchanged. STIL2 has no airtightness or ground data, so
  those stay as they were.
- Each wall keeps its layers, mass and heat capacity. One layer carries an equivalent
  conductivity that gives the STIL2 U: the masonry in SE.01, and the wool share of the stud
  layer in SE.02. The SE.01 window reuses the TABULA original timber window (U 2.30). Both
  windows keep period two-pane optics. Standard and advanced are unchanged.
- These are values from a measured stock survey. They were not fitted to measured heating.

Tested against measured EPC heating on 25 November 2026. Each test was pre-registered and
scored once.

- **School SE.01** (287 buildings): match rose from 50.5 % to 61.3 % (42 gained, 11 lost,
  p 2e-5), and skill over chance from +2.6 to +9.0 points. With EPSM reading EPCs that tick
  FTX together with another system as FTX, match was 63.4 % and skill +10.2. There are no
  unused school SE.01 buildings, and the change was chosen on this cohort.
- **School SE.02** (198 buildings, held out; with the same ventilation reading): match rose
  from 63.1 % to 70.7 % (27 gained, 12 lost, p 0.02), and skill from +6.0 to +11.1.

## What validation is not

- **Not calibration.** No catalogue parameter is adjusted to fit individual
  buildings. Renovation state, hidden retrofits, airtightness and ventilation
  performance are unknown, which is why three states are compared.
- **Not a ground model check.** Ground heat transfer is computed by `epsm_core` /
  `epsm_rc` from the nominal floor assemblies.
- **Not a gate on individual buildings.**

Inside this package, the main fabric check is agreement with TABULA (walls,
thermal top and windows within ±20 %); see [sanity checks](sanity.md).

## Reference buildings

Before cohorts are run, a single well-documented building (known geometry and a
measured annual or heating-season space-heating value) should pass the same
three-state test. No such building is available: the school in
`evidence/fridhemsskolan_2017_school.md` has one district-heating meter for nine
buildings, including hot water, and its geometry gives areas only.
