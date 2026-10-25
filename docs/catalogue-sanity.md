# Catalogue sanity checks

Sanity checks assess representative original-era construction and declared
normal-use operation. An archetype represents plausible construction for its
era; it is not a verified individual building. Checks calculate forward from
stored materials and assemblies. They never change the catalogue, repair a
construction, or solve layer thicknesses from target U-values.

## Run the checks

```python
from epsm_data import Catalogue, check_catalogue, load_sanity_fixture

catalogue = Catalogue.load()
report = catalogue.sanity_report()
assert report == check_catalogue(catalogue)

# Capture the same explicit reference bundle for a reproducible comparison.
fixture = load_sanity_fixture()
report = check_catalogue(catalogue, fixture=fixture)
print(report["summary"])
print(report["readiness"])
```

`check_catalogue` also accepts a canonical reference mapping or an explicit
resolved mapping. Canonical references first resolve against the pinned local
cache, which retains complete upstream files and separate custom thermal records.
An exact source link preserves physical values; the `epsm-custom` namespace marks
unmatched or modified grades without treating their properties as measured stock
evidence. Property mutations use the resolved form, so invalid new authoring can
produce findings even when `Catalogue(...)` would reject it.
An invalid graph can prevent forward calculations; dependent checks must then
report missing or not-assessed information rather than claim agreement.

```python
payload = catalogue.resolved_dict()
material_id = next(iter(payload["materials"]))
payload["materials"][material_id]["name"] = ""
report = check_catalogue(payload)
assert any(item["rule_id"] == "material.name" for item in report["findings"])
```

The original catalogue is unchanged. Findings are plain JSON-compatible data.

```sh
epsm-catalogue --sanity
epsm-catalogue --sanity --check
epsm-catalogue --path catalogue.json --sanity --fixture src/epsm_data/datasets/sanity --check
```

Without `--check`, the command prints its report for inspection. With `--check`,
any `error` or `missing` finding makes the command exit nonzero. Review findings
are nonblocking, but the report remains `review`, never `pass`. A zero exit code
therefore does not resolve matters that still require human judgement.
`--fixture` selects a complete explicit sanity fixture directory and requires
`--sanity`; it does not select evidence documents to discover dynamically.

## Fixed references

The canonical reference bundle is the packaged `epsm_data.datasets.sanity`
(`src/epsm_data/datasets/sanity/`):

- `policy.json`: fixture identity and explicit project acceptance policies.
- `construction_rules.json`: material families, units, thickness ranges and
  assembly-order screening rules.
- `tabula_u_values.json`: residential U-values with exact source locators.
- `tabula_renovations.json`: renovation packages and their prescribed measures.
- `nonresidential_construction.json`: explicitly labelled school/office project
  screening policies and source-limited period rationale, without TABULA targets.

Installed distributions ship the same five files. `load_sanity_fixture(path=None)`
reads this fixed bundle;
an explicit new directory supplies the same five filenames and valid policy
schema/fixture identity. Legacy four-file directories remain accepted with
school/office screens explicitly not assessed. No folder scan, network lookup, historical evidence
loader or fallback to arbitrary evidence files participates in a check.

`check_catalogue(..., fixture=...)` and `Catalogue.sanity_report(fixture=...)`
accept the default bundle (`None`), an already loaded mapping, or an explicit
fixture directory. Change policies and benchmark data deliberately in a PR,
with their tests; do not widen tolerances to hide failures.
Retained evidence remains the source material identified by the locators.

## Rules and their interpretation

| Area | What is checked |
| --- | --- |
| Names and sharing | Identifiable material names, meaningful variant distinctions, resolved references and reuse of identical physical definitions. Ambiguous or archetype-specific material labels require review. |
| Thermal sources | Resolved original or custom thermal links, matching physical values and supported units. Invalid supplied values are errors; missing values remain missing. |
| Thermal provenance | Every `EPSM_` custom thermal record declares `user_data.provenance` with a tier (`product`, `tabula`, `derived`, `standard`, `historical`, `assumption`), a basis and named sources. Missing provenance is `missing` for materials in renovation or new-build configurations and `review` for existing stock only; malformed provenance is an error and `assumption` stays a review. |
| Carbon sources | Suitable Boverket or explicit external EPD references, declared proxies and explicit non-product exemptions. Missing sources or base A1A3 production data block catalogue readiness. Unknown optional lifecycle modules require review; the consuming assessment selects its required modules. A5.1 is not complete A5. |
| Density | Comparable mass/volume densities use `abs(thermal − source) / source`. Differences above 20% require review; above 50% receive prominent review. Incomparable bases are not assessed. No density is substituted automatically. |
| Layers | Finite positive thicknesses, valid fractions summing to one and supported parallel depths. Material-specific plausible thicknesses and nominal prefabricated dimensions are screening rules; unexplained precision requires review. |
| Assemblies | Explicit side convention and construction family, plausible complete element order including component interfaces, and compatible role assignments. Missing interpretive metadata cannot establish constructability. |
| Construction sets | Required roles, compatible elements and explicit thermal top boundaries. A cold-attic ceiling is distinct from its weather roof. A reusable basement assembly does not imply basement geometry. |
| Operation | Applicable named normal-use profile, declared units/reference area, plausible gains/flows/setpoints and visible project input requirements. Fabric era does not select a historic operating schedule. |
| Original-era plausibility | Baseline construction rationale and source locators, with contradictions such as declared material first use after construction flagged as errors. A modern thermal or carbon proxy does not establish original product identity. |
| TABULA | SF/MF SE.01–SE.05, three states and three zones, with ±20% relative U-value acceptance. Compare matching thermal boundaries and calculation conventions only. Missing comparisons are not passes. |
| Residential interventions | TABULA measures, placement, nominal added insulation and replacement-window performance. Matching a target U-value alone is insufficient. |
| School/office construction | Fixed broad original-state wall/top nominal U, insulation, whole-window U and full-material capacity screens; all-state optical screens, physical boundary ownership, authored side conventions and explicit renovation rationale. Range outliers require review; they are not benchmark failures or invitations to fit layers. |
| Renovation consistency | Retained construction year, no worsening from baseline through standard to advanced, and at least one improvement per renovated state. Unchanged elements are allowed; numeric precision has an explicit small tolerance. |
| Uncovered eras and chronology | SE.06–SE.07 and non-residential constructions need a labelled plausibility assessment. Later-era thermal comparisons use an advisory 35-year intervention within the intended 30–40-year context; equality is not required. |
| SE.07 | Exactly one new-construction configuration and no renovation alternatives. |
| Generic | Explicit selection of matching MF era, zone and state with the same fabric and residential operation, labelled “Unknown building type — multifamily assumption.” No extra authored family or averaged U-values. |

Historic products without a suitable carbon source may declare
`carbon_assessment.status = "retained_existing_unmapped"` with a reason. The
check verifies that their containing baseline components remain unchanged in
every affected state and role. Eligible declarations produce a
`carbon.existing_stock` review; the material factors remain unknown. This
exception supports renovation additions while retaining existing fabric. It
does not supply zero emissions or waive factors when the product is newly
installed, removed or included in baseline LCA. Candidate EPDs can remain in
retained evidence until compatible factors are available.

Source-module availability is separate from assessment scope. Catalogue
completeness requires a resolved carbon source with base A1A3 production data;
it does not require every source to publish transport A4 or full installation
A5. Missing optional factors produce `carbon.modules` reviews with their known,
partial and missing modules. They remain absent or `null`, never zero. In
particular, Boverket's published A5.1 waste factor does not supply full A5.

A partial Boverket record may not populate the complete legacy `EmbodiedCarbon`
view, which expects both production variants, A4 and A5.1. Its published raw
modules remain available through an explicitly supplied catalogue; missing legacy
fields are not filled. External `CarbonReference.factors()` likewise exposes only
known modules. A downstream LCA must select its scope and reject unavailable
requested factors. EPSM LCA already does so per material and requested module;
Data does not duplicate that assessment policy or claim a complete LCA.

Ground floors and basement walls are not compared with TABULA. Ground heat
transfer is modelled by `epsm_core` / `epsm_rc` from the nominal assemblies and the
building's own geometry and soil. The checker only requires every configuration to
have a resolved ground-floor assembly; an absent or unresolved floor is a blocking
`construction.ground_definition` finding.

School and office screens distinguish the retained early masonry families, later
timber-frame school walls, and concrete office walls/floors. Their numeric ranges are broad engineering
review triggers, not values extracted from a national survey, regulatory limits or
measured historical distributions. Full material capacity is calculated as
`sum(area_fraction * thickness * density * specific_heat)`, including all stored
layers; it is not the effective thermal capacity used by a reduced energy model.
Low conductivity does not make timber framing or non-product air a prescribed
insulation layer. Passing these screens does not resolve `era.reference_coverage`.

The early school/office family explicitly represents an unheated basement. Its
timber/shavings `GROUND_FLOOR` is the suspended ceiling, while `BASEMENT_FLOOR`
provides a separate soil slab. Missing roles are blocking; contradictory declared
boundaries, a timber ceiling posing as the concrete soil slab, or incompatible
authored side conventions are errors. Absent interpretation metadata remains a
review. Project geometry still selects which installed interfaces exist.

A cold-attic `TOP_FLOOR` is the conditioned ceiling, separate from its `ROOF`
weather shell. Intermediate-floor `lower_room_to_upper_room` metadata agrees with
stored `bottom_to_top`; the reverse pair is equally explicit. These authored
conventions are checked before any consumer changes layer direction for export.

Whole-window optics require a source or an explicit assumption: a carbon-family
proxy or construction year alone does not establish SHGC or visible transmittance.
Renovation also needs retained-fabric, placement, accessibility and buildability
rationale. Changed layers that no longer retain the baseline sequence or additions
placed within/inside retained fabric receive review rather than an automatic claim
of constructability. No school/office layer is calibrated to a range by the checker.

Existing explicit in-memory reference mappings without the new nonresidential
table remain accepted for API compatibility, as do older explicit four-file
directories. They retain outside-TABULA and `nonres.reference_not_assessed`
findings and do not gain school/office screening coverage. Only the known new
filename may be absent from a legacy directory; no file is silently loaded from
another location. The default packaged bundle requires all five files.

TABULA's second wall also needs an evidenced boundary mapping; it must not
silently become the catalogue basement wall. An unavailable comparison or
unmapped source boundary is a nonblocking reference review, with no claim of
agreement. A source-prescribed renovation intervention that cannot be verified
still produces a missing measure finding. Identical zone constructions are
valid where their references agree.

MF SE.01 has an evidenced exception recorded in the maintained fixture: its
lowest floor is a conditioned-basement slab against soil, and `TABULA_WALL_2`
maps to the buried `BASEMENT_WALL`. The Swedish brochure prescribes 40 mm
internal wall insulation in the advanced package. The fixture checks that the
catalogue declares matching physical boundaries and that this addition follows
all retained baseline layers. Other eras receive no inferred Wall2 alias.

TABULA's ground values (BETSI inputs that already include ISO 13370 ground heat
transfer, plus cellar corrections) stay in the fixture for reference only. See
`evidence/mf_se01_ground_boundaries.json` for the source review.

SF SE.01 uses the TABULA pre-1960 AAC wall and ground-slab families, with a
representative 1950 year. Period sources support its nominal shavings-filled attic
ceiling; TABULA does not supply that original layer recipe; the source review in
`evidence/sf_se01_source_review.json` separates source measures from explicit
construction defaults. Timber panelling/framing and non-product air do not count
as prescribed insulation merely because their conductivity is low.

A shared layer can serve different functions in different assemblies. A
component's layer slot may therefore declare `layer_function`; this takes
precedence over the shared layer's default. Both values use the same validated
function vocabulary. Function metadata does not create a new physical layer or
permit duplicate physical components.

A material may select `carbon_source_grade` when a source describes several
product grades without one volumetric conversion. The maintained
`construction_rules.json` fixture holds the corresponding
`density_grade_references`, including the exact source field, quotation, density,
unit and volume basis. The checker verifies the retained source quotation and
source identity before comparing densities. A source's existing conversions take
precedence. This supports the published EPS 100 grade and the selected Supafil
EPD without substituting any thermal density or adding a universal density to a
multi-grade resource.

Density margins and broad construction screens are project policies, not Swedish
regulatory tolerances. These checks do not certify structural, fire or moisture
compliance. Any substantive correction to a stored construction belongs in a
separate reviewed change.

## Read the report

Each finding includes a stable `rule_id`, `severity`, `path`, `actual`,
`expected`, and `affected_archetypes`. Each affected entry identifies the donor
`archetype_id`, state and climate zones. `generic_fallback_affected` indicates
that MF-based generic selections inherit the issue. One shared material finding
therefore exposes every affected construction assignment.

- `error`: contradictory or invalid information, or a failed acceptance rule.
- `missing`: required information or a reference comparison is unavailable.
- `review`: a plausibility concern or explicit not-assessed/context-only item
  requiring judgement; it never becomes an automatic pass.

`summary` reports counts and overall `blocked`, `review` or `pass` status.
`readiness` separates `thermal_inputs`, `carbon_inputs`, `operating_defaults` and
`reference_agreement`. It is possible to have valid thermal inputs while carbon
coverage or reference agreement is blocked. None of these alone establishes a
complete project simulation.

`project_requirements` lists the selected operating profiles, reference-area
basis and outstanding project inputs. Physical extent, Atemp/reference area,
calendar where required, installed ventilation/HVAC, weather and appropriate
ground conditions remain explicit building inputs. A missing project calendar
is not a missing fabric default.

Source and construction reviews remain after the blocking inputs resolve.
These include project boundary choices, source-convention limits, representative
assumptions and the sand-fill Tagene proxy's undeclared A4/A5. Module availability
remains visible as review; absent base production or source data blocks readiness.
Inspect the current report for exact counts and affected assignments.
