# Catalogue sanity fixture

This packaged directory is the maintained source of the sanity checker’s expectations.
Its values are independent of the current `catalogue.json`: calculating a new
catalogue value does not update a reference or make a failing check pass.

| File | Expectations |
| --- | --- |
| `policy.json` | User-approved tolerances, severity meanings and generic/MF contract. |
| `construction_rules.json` | Material-family thickness ranges, prefab precision, units and explicit assembly roles. These are screening policies, not regulatory certification. |
| `tabula_u_values.json` | SF/MF SE.01–SE.05 element U-values, all states and three zones, with source variants and workbook cell locators. |
| `tabula_renovations.json` | Actual renovation measures, nominal additions, source locators and package-to-era mappings. |
| `nonresidential_construction.json` | Fixed broad school/office project screens, explicit provenance, period coverage, optics and soil-floor assumptions. These are review policies, not recovered TABULA benchmarks. |


Scenario inputs used by the tests live in `tests/fixtures/sanity_cases/`. Runtime
checks use this bundle unless a caller deliberately supplies another fixture
directory.

The loader uses these five fixed filenames. It does not discover files, inspect
arbitrary working directories or choose targets from the database being checked.
Older explicit four-file directories remain accepted, with school/office screens
reported as not assessed; the missing new table is never loaded from a default
location. The packaged bundle always contains all five.

The TABULA tables were extracted from the retained original observations in
`evidence/betsi_review/audit.json`, `evidence/sfh_tabula_measures.json` and
`evidence/mfh_tabula_measures.json`. Per-row locators retain the exact source.
The comparison never reads those larger evidence files at runtime. Equivalent
SFH source variants are collapsed with both variant identities retained.

Coverage is deliberately limited: no invented SE.06/SE.07, office or school
TABULA targets. Insulation `U_measure` is not a final renovated assembly target.
The nonresidential table separately labels broad engineering review ranges for
the user-authored masonry, school timber-frame and office concrete period families. Its ranges do not establish
historical prevalence or independent source agreement. Contradictory physical
boundaries are errors; plausible-range departures and unverified representative
assumptions remain review findings. Synthetic mutation tests cover missing soil
slabs, timber ceilings misassigned as soil, directional contradictions, implausible
full-material capacity and optics, and loss of baseline fabric during renovation.
Every authored configuration receives a `ground.project_inputs` review when its
nominal floor assembly resolves. Project geometry, soil and the selected ground
boundary method are declared consumer inputs, not missing catalogue fabric.
The independent reporting case expects 76 physical configurations across 28
families; generic selections inherit their MF donor findings. An absent physical
floor or unavailable forward calculation remains a blocking missing definition.
Ground U-values require matching geometry/reference conventions; unavailable
comparisons remain nonblocking reviews and never become acceptance passes.
Unmapped TABULA Wall2 is a reference-mapping review; a prescribed but unverified
renovation measure still produces a missing intervention finding.
MF SE.01 has an evidenced conditioned-basement floor
and wall-2 mapping, declared in each target's `boundary_comparison`. Catalogue
metadata must match its physical boundary, role and layer convention before a
measure can use that mapping. The original ground-inclusive BETSI inputs received
subsequent TABULA Cellar corrections; these observed U-values remain unchanged
but are explicitly source-incompatible with nominal material-layer U-values.
They produce nonblocking source-convention and not-assessed reviews when the
physical mapping resolves, never an acceptance pass. Missing or contradictory
physical boundary metadata remains blocking. Other wall-2 mappings remain unassessed. A cold-attic conditioned
ceiling is distinct from the weather roof.

The MF SE.01 advanced package's `measure_overrides` establishes the brochure's
internal/warm-side 40 mm wall-2 placement. Only the placement and its exact source
locator may override a measure; nominal depth and U-value cannot be overridden.

To change an expectation, edit the table in a PR, retain its source/basis, and run the fixture and checker tests.
Do not expand tolerances or rewrite benchmarks merely to conceal a finding.

Catalogue corrections are separate edits reviewed on their merits. Findings
are review inputs, not automatic repair instructions. Tests verify source
expectations and synthetic bad inputs; a corrected catalogue can have no errors
while carbon gaps and project limitations remain visible.

`tests/fixtures/sanity_cases/reporting.json` includes a deliberate layer-thickness regression probe.
The test changes an in-memory copy and checks that a deviation is reported without
repairing it. Negative coverage therefore does not require a known defect to be
retained in the accepted catalogue.
