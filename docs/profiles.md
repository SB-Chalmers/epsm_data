# Operating profiles and system templates

An archetype describes the building fabric. How the building is used and
ventilated comes from two further inputs:

- an **operating profile**: occupancy, setpoints, gains, hot water and
  ventilation rates;
- a **system template**: the ventilation system and heat recovery, plus window
  areas per facade.

Both are immutable, read offline from `src/epsm_data/datasets/profiles/`, and
can be reused across archetypes. The code is in `epsm_data/profiles.py`
and `epsm_data/templates.py`.

## Normal use (Sveby)

```python
from epsm_data import available_operating_profiles, select_operating_profile

profiles = available_operating_profiles()
profile = select_operating_profile("multi_family")
assert profile.values["use"]["dhw_kwh_m2_year"] == 21
print(profile.values["requirements"])
```

`select_operating_profile(building_type, standard="sveby", version=None, era=None)`
supports `single_family`, `multi_family`, `office` and `school`.

| Use | Source |
| --- | --- |
| Single- and multi-family | Sveby *Brukarindata bostadshus* 2.0, 2024 (single-family uses the residential values, as the source allows) |
| Office | Sveby *Brukarindata kontor* 1.0, 2012 |
| School | Sveby *Brukarindata undervisning* 1.0, 2016 |

Sveby intensities are per m² **Atemp**, the heated floor area. Office and school
schedules need a calendar with active dates; a representative study calendar is
fine. Core expands the schedules and applies the values to the building.

`load_operating_profile(name)` loads a profile by name. `generic_other` is a
screening assumption for a use the catalogue does not cover.
`load_standard_record(name)` returns the underlying source data as plain JSON.

## Measured stock use

Sveby describes normal use. Existing Swedish buildings run warmer and ventilate
more than that. `standard="measured"` returns the Sveby profile with measured
stock values substituted. Use it to compare simulations of existing buildings
with measured energy; use Sveby for compliance-style calculations.

```python
measured = select_operating_profile("multi_family", standard="measured", era="SE.03")
assert measured.values["use"]["heating_setpoint_c"] == 22.5
```

| Use | Input | Sveby | Measured | Source |
| --- | --- | --- | --- | --- |
| Multi-family | Heating setpoint | 21 °C | 22.2–23.0 °C by era | BETSI (Boverket 2010) table 3.6 |
| Multi-family | Self-draught total air change | 0.5 ACH + infiltration | 0.39 ACH in total | BETSI section 4.2.2 |
| Office | Ventilation flow and hours | 1.3 L/(s m²), 07–19 | 1.6 L/(s m²), 06–20 | Sveby kontor 1.0, named operator examples |

Each value passed the cohort test in [validation](validation.md) on a
calibration and a hold-out sample. The housing values are measured stock surveys.
The office values are named operator examples in Sveby kontor 1.0 (p. 12), not a
survey: Brostaden's 1.6 L/(s m²) and Skanska's 06–20. SE.06 and SE.07 postdate BETSI and use its
newest class (1996–2005).

The self-draught value already includes envelope infiltration. It is stored in
`values["measured_use"]["ventilation"]["S"]`. The consumer sets natural
ventilation to this total minus the building's infiltration, with a floor of
0.05 ACH. Single-family houses and schools have no measured value and return the
Sveby profile with a note.

## Hot water for energy declarations (BEN)

```python
from epsm_data import select_dhw_profile

ben = select_dhw_profile("multi_family", purpose="epc_normal_use")
assert ben.values["dhw_kwh_m2_year"] == 25
assert ben.values["area_basis"] == "Atemp"
```

This is the useful hot-water heat in BEN (BFS 2016:12, amended by BFS 2017:6),
before production losses and excluding circulation and storage losses. It
supports `single_family`, `multi_family`, `office`, `school` and
`non_residential`. `purpose` must be given. It does not change the Sveby profile.

## Heat that an EPC includes

```python
from epsm_data import select_epc_comparison_terms

terms = select_epc_comparison_terms("multi_family", municipality_code="1485")
assert round(terms.values["window_airing_kwh_m2_year"], 2) == 3.6
assert round(terms.values["hot_water_circulation_kwh_m2_year"], 2) == 8.33
```

Measured EPC heating includes energy that a simulation does not. These terms are
kWh/m² Atemp per year of heat, before the heating system's efficiency or COP:

| Use | Window airing | Hot-water circulation |
| --- | --- | --- |
| Housing | 4 × Fgeo (Sveby bostadshus 2.0, p. 9; BFS 2026:9 Tabell 1) | BEN hot water × (1/0.75 − 1) (BEN 3 kap. 3 §) |
| School | 4, no Fgeo (Sveby undervisning 1.0, chapter 6) | None: to be measured |
| Office | 0, negligible (Sveby kontor 1.0, p. 13) | None: no default |

Housing needs `municipality_code`. These are definitions: which types a
comparison applies them to is its own decision, see [validation](validation.md).

## Heat-pump delivery

```python
from epsm_data import heating_delivery_template

template = heating_delivery_template("heat_pump")
```

An `HVACTemplate` with the Swedish field-average seasonal COP of 2.75 (field SPF
2.7–2.9, Haglund Stignor et al. 2015). There is one value for every pump type and
era: a modern 3.9 for new ground-source houses was tested and rejected.

## Custom profiles

`OperatingProfile(profile_id, values, source_references=(), notes=())` freezes
JSON-compatible values. For a custom Core handover, place partial `use`,
`airflow` and `facade` inputs under `values["building_assumptions"]`.
`HVACTemplate` carries system inputs the same way. `to_dict()`, `from_dict()` and
`with_changes()` work as on the other classes.

## Ventilation templates

Any archetype can use any ventilation system. Pass the building's observed
system, for example its energy-declaration (EPC) ventilation type; without it,
the era default below applies.

```python
archetype = catalogue.for_year("multi_family", 1970, state="existing", ventilation="FTX")
archetype.hvac_template          # epsm.ventilation.FTX_075
catalogue.ventilation_options("mf_se02", state="existing")
```

| Code | Template | Airflow |
| --- | --- | --- |
| S | `epsm.ventilation.S` | Self-draught (natural), 0.5 ACH (BBR 0.35 L/(s m²) at 2.5 m ceiling height), no fans |
| F | `epsm.ventilation.F` | Mechanical exhaust, profile flow, no heat recovery |
| FT | `epsm.ventilation.FT` | Mechanical supply and exhaust, profile flow, no heat recovery |
| FTX | `epsm.ventilation.FTX_060` / `_075` / `_080` | Supply and exhaust with heat recovery efficiency 0.60 / 0.75 / 0.80 |

The template covers airflow only. Airflow inputs are merged in the order
operating profile → template → envelope, so the profile keeps its occupied
ventilation rates and `EnvelopePerformance` keeps infiltration.

**Observed system.** S, F and FT are used as observed. An observed FTX gets
recovery 0.75 before 1976 (it must be a retrofit), 0.60 in 1976–2005, 0.75 in
2006–2021 and 0.80 from 2022. An exhaust-air heat pump counts as F; the heat
pump is a heating-system input.

**Era default**, used only when the system is unknown:

| Era | Single-family | Multi-family | Office | School |
| --- | --- | --- | --- | --- |
| SE.01 | S | S | S | S |
| SE.02 | S | F | FT | F |
| SE.03 | F | F | FT | FT |
| SE.04 | F | F | FTX 0.60 | FTX 0.60 |
| SE.05 | F | F | FTX 0.60 | FTX 0.60 |
| SE.06 | FTX 0.75 | FTX 0.75 | FTX 0.75 | FTX 0.75 |
| SE.07 | FTX 0.80 | FTX 0.80 | FTX 0.80 | FTX 0.80 |

The Standard renovation keeps the existing system. Advanced installs FTX 0.80.
These are period assumptions from typical Swedish practice, not measured stock
shares. The rules are in `datasets/profiles/ventilation_templates.json`.

## Window-to-wall ratios

`catalogue.facade_assumptions(archetype_id)` returns a default window-to-wall
ratio (window area ÷ gross facade area) and one per orientation. A facade
belongs to the sector its outward normal faces: N 315–45°, E 45–135°,
S 135–225°, W 225–315°.

| Type | Default | N | E | S | W | Basis |
| --- | --- | --- | --- | --- | --- | --- |
| Single-family | 0.18 | 0.12 | 0.17 | 0.26 | 0.17 | TABULA SE reference house |
| Multi-family | 0.24 | 0.22 | 0.23 | 0.28 | 0.23 | TABULA SE reference block |
| Office | 0.30 | 0.30 | 0.30 | 0.30 | 0.30 | EPSM assumption |
| School | 0.25 | 0.25 | 0.25 | 0.25 | 0.25 | EPSM assumption |

The four orientation values average to the default, so a model can use either.
Ratios are the same for every era and state. The values are in
`datasets/profiles/facade_assumptions.json`.

The [operation and systems notebook](../examples/02_operation_and_systems.ipynb)
shows these selections.
