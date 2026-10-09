# Matrix application and unresolved building prediction

Added 3 October 2026; updated 9 October 2026. The frozen DB 1.5.0 / LoD2 v1.4 baseline contains 90 canonical construction states and
1,080 category/era/climate/state/ventilation classification slots. These are
source-evidenced constructions, not 1,080 independently calibrated buildings.

`epsm_data.resolve_building_archetype` selects a unique canonical category/era
parent, then permits component states for wall, roof, ground, basement wall,
intermediate floor, window and airtightness. Every component selection requires
an independent source. A window replacement leaves the walls and infiltration
unchanged. Source descriptions establish why a representative is selected; they
do not assert that catalogue values are measurements of that actual building.

```python
from epsm_data import resolve_building_archetype

native = resolve_building_archetype(
    category="multi_family", construction_year=1965,
    climate_zone="SE.Zone3", ventilation="F", default_state="existing",
    component_states={"window": "standard"},
    component_sources={"window": "independent renovation record, windows only"},
)
```

Use a climate-zone code from your audited zone mapping. Inspect `assignment`,
`component_nominal_bundles` and `requirements` before building a Core spec.
The resolver supplies envelope/glazing and independent infiltration. Roof
topology is a library hint; the real geometry/thermal boundary must be verified.
The default state is explicitly assumed. It cannot determine renovation history
from construction year or a heating residual. Existing means original-era fabric,
not proof that the building has never been renovated.

Run the read-only matrix audit with:

```sh
python -m epsm_data.matrix_audit --output evidence/matrix-application-audit.json
```

It refuses to overwrite a file, retains original sources/caveats/readiness and
exports nominal and reference properties. Ground references and nominal layers
are different physical quantities; their percentage difference is informational,
not a calibration target. Element availability does not prove presence in a
building. Audit-row simulation readiness remains pending. The separate completed
MF SE.02 Existing/F/district-heat retrospective study is provisional; see
[matrix freeze](frozen-baseline.md) and [validation results](mf-se02-data15-validation.md).

## Fine-tuning investigations

| Question | Evidence required before changing data | Current disposition |
|---|---|---|
| MF SE.02 existing window U=2.8 versus diagnostic candidate 2.2 | Whole-window definition, frame/glass/solar properties, renovation records and independent buildings | v1.4 provisionally uses 2.2; historical reference 2.8 remains documented. Independent validation is pending. |
| Joint renovation state versus component history | Independent records for windows, walls, roof and airtightness | Resolver supports separate components; residual-based state choice is excluded. |
| Basement/attic and ground contribution | Heated extent, construction role and exchange/soil evidence | Core receives native boundaries and exchange. Reference layers stay fixed; cohort resistance variations are bounded effective assumptions. |
| Infiltration versus ventilation and recovery | Definitions/units, measured or evidenced operating flows, n50 conversion model if used | Leakage stays separate; no stock air-exchange substitution. |
| Transferred internal/basement constructions | Source applicability, category and era coverage | Audit retains transferred evidence; no precision or confidence interval invented. |
| Wide modern-era or non-residential heterogeneity | Representative independent properties and physical attributes | Separate predictive families when justified; do not split eras solely by lower training error. |
| Area and operational bias attributed to fabric | Verified Atemp/geometry, use calendars, gains and target accounting | Resolve application evidence before changing material values. |

Core owns Sveby operation profiles and delivery accounting. Workflows owns
property-separated experiments and held-out evaluation. Numerical catalogue
changes require independent physical evidence plus frozen predictive comparison;
cohort profiles do not modify reference datasets or establish <20%/<10%
building error. See the Workflows implementation log for experiments and failures.

### Reconcile archived extraction (2026-10-03)

`python -m epsm_data.extraction_audit --extraction PATH --review-directory PATH
--output NEW_FILE` creates a read-only register joining the hash-pinned full
extraction, normalized records, archived comparisons and historical v1.3 calibration. Current values are pinned
by the [DB 1.5.0 freeze](frozen-baseline.md).
The extraction must match `review_decisions.json` before positional annotations
are used. Repeated case families, contextual exclusions, uncertain eras and
nominal/effective boundaries retain their reviewed classifications. Historical
proposals are shown alongside current values, never reapplied. The 296 extraction
records and 630 thermal comparisons contain no annual measured-energy validation.


### Database v1.4: provisional multifamily window default

Existing multifamily SE.02 now uses whole-window U=2.2 W/(m²K), replacing 2.8.
Other uses, eras, states, optics, carbon proxies and infiltration are unchanged;
generic/source definitions keep their historical window. The window-only
retrospective diagnostic improved <20% coverage from 8/12 to 9/12 and MAE from
18.138 to 15.011 kWh/(m² year). Independent validation remains pending. The joint
10/12 result also changed wall/roof thickness and ventilation and is not a claim
for this window update. Package version is 0.3.0.dev1; BASELINE.json pins v1.4
resource checksums. See [release evidence](../evidence/lod2_v1_4/README.md).


### Effective cohort profiles (current v2, 2026-10-05)

`epsm_data.cohorts.assign_cohort(descriptors, bundle)` performs target-free medoid assignment using the frozen training transform. Energy observations and residuals are forbidden. Unsupported parents, missing descriptors, out-of-domain distances and unvalidated profiles return the parent fallback. `allow_provisional=True` explicitly opts into experimental profiles.

`apply_cohort_profile(spec, profile, locked_parameters=...)` applies source-recorded, bounded effective assumptions to a native Core spec without mutating it. Independently evidenced inputs can be locked. Geometry, climate, reference material conductivity/density and Atemp remain fixed. These cohort assumptions describe effective surviving-stock behavior; they do not rewrite the reference database or establish actual component renovation histories. Unknown controls and out-of-bound values raise errors. The Workflows cohort-transfer protocol freezes property-separated validation and retains failed predictions in the accuracy denominator. All four uses and six eras are covered by native baseline-construction contract tests; measured transfer support is determined separately.

The current [v2 profile](../cohort_profiles/2026-10-05-v2/README.md) supersedes
the ACH-based v1 profile. Final validation selected baseline with no fitted
overrides. `cohort_profiles/current.json` identifies the current artifact.
