# Sanity checks

The sanity checks screen the catalogue for errors and gaps. They calculate
forward from the stored materials and layers and compare the results with fixed
references, such as TABULA U-values. They never change the catalogue, repair a
construction or solve layer thicknesses from a target U-value.

An archetype is a plausible construction for its era, not a verified building.
A finished report shows what was checked and what still needs judgement. The
code is in `epsm_data/sanity/`: `catalogue.py` runs the checks; `physics.py`,
`references.py` and `nonresidential.py` hold the screens.

## Run the checks

```python
from epsm_data import Catalogue, check_catalogue, load_sanity_fixture

catalogue = Catalogue.load()
report = catalogue.sanity_report()
assert report == check_catalogue(catalogue)

fixture = load_sanity_fixture()          # the packaged reference bundle
report = check_catalogue(catalogue, fixture=fixture)
print(report["summary"])
print(report["readiness"])
```

`check_catalogue` also accepts a catalogue in its reference or resolved form (see
[saved forms](catalogue.md#saved-forms)). Use the resolved form to test an edited
property. It reports invalid values as findings, where `Catalogue(...)` would
refuse to load them:

```python
payload = catalogue.resolved_dict()
material_id = next(iter(payload["materials"]))
payload["materials"][material_id]["name"] = ""
report = check_catalogue(payload)
assert any(item["rule_id"] == "material.name" for item in report["findings"])
```

From the command line:

```sh
epsm-catalogue --sanity
epsm-catalogue --sanity --check
epsm-catalogue --path catalogue.json --sanity --fixture src/epsm_data/datasets/sanity --check
```

`--check` exits nonzero on any `error` or `missing` finding. Review findings do
not fail the command, but the report status stays `review`, never `pass`.
`--fixture` selects another reference directory and requires `--sanity`.

## Reference bundle

The checks read only the fixed bundle in `src/epsm_data/datasets/sanity/`:

| File | Contents |
| --- | --- |
| `policy.json` | Bundle identity and the project's acceptance policies |
| `construction_rules.json` | Material families, units, thickness ranges and layer-order rules |
| `tabula_u_values.json` | Residential TABULA U-values with source locators |
| `tabula_renovations.json` | TABULA renovation packages and their measures |
| `nonresidential_construction.json` | School and office screening ranges and period rationale |

`load_sanity_fixture(path=None)` reads the bundle. Another directory must supply
the same five files. An older four-file directory still loads, with school and
office screens reported as not assessed. Nothing else is read: no folder scan,
network lookup or evidence file. Change references and tolerances in a reviewed
pull request with their tests; do not widen a tolerance to hide a failure.

## What is checked

| Area | Check |
| --- | --- |
| Names and sharing | Clear material names, resolved references, identical definitions reused |
| Thermal sources | Each material links to a thermal record with matching values and supported units |
| Thermal provenance | Each record declares a tier, basis and sources ([tiers](sources.md#thermal-records)). Missing provenance is `missing` for renovated or new-build materials and `review` for existing stock; `assumption` is always a review |
| Density | `abs(thermal − source) / source` above 20 % is a review; above 50 % a prominent review |
| Layers | Positive thicknesses, fractions that sum to one, plausible thicknesses for the material |
| Assemblies | Stated side convention and construction family, a plausible layer order |
| Construction sets | Required roles present; cold-attic ceiling separate from roof |
| Ground | Every configuration has a resolved ground floor (`construction.ground_definition`). Ground floors and basement walls are not compared with TABULA; `epsm_core` / `epsm_rc` model ground heat loss |
| Operation | A named profile with units, reference area and plausible values |
| Original era | Rationale and source locators; a material used before its first year is an error |
| TABULA | Single- and multi-family SE.01–SE.05, all states and zones: U-values within ±20 % for matching boundaries |
| Residential renovation | TABULA measures, their placement, added insulation and window performance; a matching U-value alone is not enough |
| Schools and offices | Broad screens on original wall and roof U, insulation, window U, optics and thermal mass |
| Renovation order | Existing → Standard → Advanced never gets worse, and each renovated state improves something |
| SE.06–SE.07 | A labelled plausibility assessment; SE.07 has exactly one configuration |
| Generic | Uses the matching multi-family archetype unchanged |

Density margins and school and office ranges are project screening rules, not
regulations or survey data. The checks do not cover structure, fire or moisture.
Thermal mass in the school and office screen is the full stored capacity,
`sum(area_fraction × thickness × density × specific_heat)`, not the effective
capacity of a reduced energy model.

### Carbon

A material needs a Boverket or EPD carbon source with A1–A3 production data;
otherwise the catalogue is not ready. Missing optional modules, such as transport
(A4) or full installation (A5), give a `carbon.modules` review and stay `null`,
never zero. Boverket's A5.1 waste factor is not a full A5. The consuming life-cycle
assessment (`epsm_lca`) chooses the modules it needs and rejects missing ones.

A material marked `retained_existing_unmapped` gives a `carbon.existing_stock`
review. The check confirms that the components containing it are unchanged in
every state. Its factors stay unknown.

### Documented exceptions

- **MF SE.01** has a heated basement. Its lowest floor is a slab on soil, and
  TABULA's second wall maps to the buried `BASEMENT_WALL`. The advanced package
  adds 40 mm of internal wall insulation, as the Swedish TABULA brochure states.
  See `evidence/mf_se01_ground_boundaries.json`. No other era maps TABULA's second
  wall.
- **SF SE.01** uses TABULA's pre-1960 aerated-concrete wall and slab, with 1950 as
  the representative year. Its shavings-filled attic ceiling comes from period
  sources; see `evidence/sf_se01_source_review.json`.
- A shared layer can take a different `layer_function` in each component.
- A material can select `carbon_source_grade` when a carbon source covers several
  product grades. The matching density, quotation and source are listed under
  `density_grade_references` in `construction_rules.json`.

Timber framing and air gaps never count as insulation, whatever their
conductivity.

## Read the report

Each finding has a `rule_id`, `severity`, `path`, `actual`, `expected` and
`affected_archetypes`. Each affected entry names the archetype, state and climate
zones. `generic_fallback_affected` shows that generic selections inherit the
finding.

| Severity | Meaning |
| --- | --- |
| `error` | Invalid or contradictory information, or a failed acceptance rule |
| `missing` | Required information or a reference comparison is unavailable |
| `review` | Needs judgement, or was not assessed; never an automatic pass |

`summary` gives the counts and an overall `blocked`, `review` or `pass`.
`readiness` reports `thermal_inputs`, `carbon_inputs`, `operating_defaults` and
`reference_agreement` separately; thermal inputs can be ready while carbon is
blocked. `project_requirements` lists the inputs the building must still supply:
geometry, Atemp, a calendar where required, systems, weather and ground
conditions.

A missing comparison is never a pass. Fix a stored construction in a separate,
reviewed change.
