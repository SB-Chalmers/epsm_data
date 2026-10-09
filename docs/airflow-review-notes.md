# Airflow definitions and review history

Current frozen baseline: **DB 1.5.0**, 9 October 2026. Use the MF area-rate
section below for current defaults; the DB 1.4.1 section records the earlier
source-volume review. The completed 5 October validation retained the baseline
with no fitted overrides; see [results](mf-se02-data15-validation.md) and
[freeze scope](frozen-baseline.md). Historical verification results below describe
their dated review, rather than a fresh check of the current freeze.


### 2026-10-04 — airflow source and reference-volume review (DB 1.4.1)

Reviewed Sveby Brukarindata bostäder 2.0 (2024-11-11), chapters 5–6:
https://www.sveby.org/wp-content/uploads/2024/11/Sveby-brukarindata-bostadshus-2.0-241111.pdf
Residential 0.35 L/s/m² is normal-use ventilation, not extra infiltration or an
observed flow for every existing building. Window airing is a separate annual
energy allowance with prescribed geographical/system adjustments. No historical
era infiltration replacement was established. No airing allowance is automatically
added here: the benchmark's observation/normalisation boundary must be checked.

Scanned all 296 records of ARCHIVE/freeze-2026-09-30/extraction results.json.
44 matching statements are retained with JSON pointers and source metadata in
packaged parametric/airflow_review.json. Pressure-test values, renovation scenarios,
ambiguous ACH and night ventilation were not promoted to national leakage inputs.
The malformed older extraction copy was not used as an authoritative dataset.
Repeated records do not become independent evidence.

The original TABULA calculation method provides stronger unit evidence:
https://episcope.eu/fileadmin/tabula/public/docs/report/TABULA_CommonCalculationMethod.pdf
Equation (7), printed pp.12–13 / Table 4, uses the additional infiltration
surcharge on A_C_ref × 2.50 m. The archived workbook formulas reference
Tab.Const.Infiltration, confirming these matrix values are the infiltration
surcharge, rather than TABULA's separate use-related air-change default.
The 2.50 m is a calculation convention, not measured building clear height.
Core's geometry volume must not silently replace this source reference volume.
Atemp is not asserted to equal TABULA A_C_ref; any mapping is caller-owned.

Implemented infiltration_handoff and optional explicit reference-area/model-volume
inputs in resolve_building_archetype. They preserve volumetric source flow and
return the compatible Core ACH plus an audit. Legacy calls still return source
ACH, now labelled conversion_required. All matrix infiltration assignments are
marked assumed; office/school/generic residential inheritance is explicit. Updated
92 captured infiltration metadata records and DB patch version to 1.4.1; no
numerical matrix targets, envelope constructions, gains or schedules changed.

The conversion does not settle wind/stack/exhaust pressure coupling. The prior
Gothenburg 0.5 multiplier was fitted against the old volume convention; do not
stack it onto this conversion without a new campaign/profile validation. Earlier
campaign files/profiles and historical claim registers remain unchanged. No new
building accuracy result is claimed.

Verification: full EPSM Data suite passed, 256 tests in254.87 s, from the Data repository with localhost socket permission for explorer integration tests. All1080 slots retain numerical targets; packaged baseline hashes and git diff --check pass. Targeted conservation/source-staleness/application tests passed. No EnergyPlus runs or migration of existing campaign inputs were performed.


## MF starting values, DB 1.5.0, 2026-10-04

Native additional infiltration is in L/s/m² Atemp. SE.01–02 existing: .20;
SE.03–06 existing: .10; standard all eras: .10; advanced SE.01–02: .10,
SE.03–04: .05, SE.05–06: .025. Values are identical across S/F/FT/FTX.
Older-existing .20 is a practical engineering start motivated by the known
SE.02 exhaust cohort's inferred range .157–.274. Remaining era/state ratios
are retained assumptions, not independently fitted or measured defaults.
Sveby supplies ventilation/airing guidance, not these infiltration rates.

The ACH compatibility representation is q × 3.6 / 2.5. Native Core receives
envelope_infiltration_ach=0 and envelope_infiltration_l_s_m2=q; explicit load
reference area must equal Atemp. F/FT ventilation .35 remains separate; FTX
recovery affects mechanical flow only. S uses natural exchange without adding
mechanical ventilation. Exhaust pressure coupling remains unresolved.

MF-only overrides leave SF and borrowed nonresidential targets unchanged.
Historical source evidence and frozen campaign inputs remain immutable. Old
cohort profiles cannot be stacked onto the new area-rate baseline without refit.
Quick-test selection/results: epsm_workflows/output/mf-airflow-starting-values-2026-10-04.

Quick rerun result: six distinct SE.02 F properties selected by Atemp quantiles
before targets; five accepted pairs. MAE 22.43 → 8.20 kWh/m²/year, bias
+22.43 → +1.36, <20% 2/6 → 4/6, <10% 0/6 → 3/6. One building
failed strict numerical checks in both cases and remains in the denominator.
Retrospective, small-sample evidence: later-era/state/system defaults are not
validated by these measurements. Native S/F/FT/FTX smoke tests verified identical
.20 leakage flow, separate .35 ventilation, mechanical-only FTX recovery.
