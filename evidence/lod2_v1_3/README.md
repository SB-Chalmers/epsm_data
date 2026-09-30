# LoD2 v1.3: evidence-qualified construction library

V1.3 supplies seven optional construction roles in all 90 canonical states,
covering 1,080 classification slots. Geometry determines whether any role is
present. These are representative EnergyPlus-compatible constructions, not
empirically validated buildings.

The update replaces the unsupported 50 mm soft wood-fibre basement lining with
an assumed 15 mm mineral finish, preserves the concrete or masonry structural
family, and supplies missing Office/School basement roles using a transferred
200 mm concrete / 15 mm mineral-finish family. Existing 300 mm concrete and
brick/plaster families remain distinct. No basement renovation or excavation is
assumed: its corrected baseline is retained independently in all three states.
The finish depth is an engineering selection, not a BETSI observation.

There are 84 changed physical basement recipes: 48 former soft-board recipes,
six formerly plain-concrete recipes with an added finish, and 30 newly available
Office/School recipes. Six masonry/plaster recipes are physically unchanged.
All other physical recipes, material properties, and renovation inventories are
retained from v1.2. No unsupported era-specific insulation is introduced merely
to make basement rows look different.

## LoD1 and evidence

All 630 thermal values and 90 background infiltration values are unchanged.
Each now carries evidence metadata, including source/derivation, construction
basis, applicability, and qualitative limitations. All seven thermal properties
also expose `evidence.nominal_u_value`, computed from the selected construction.
For ground roles this is deliberately separate from the legacy effective
`value`; neither field is a new soil or geometry calculation.

`claims.json` records all 720 property decisions plus layer and material claims;
`decisions.json` provides the before/after construction ledger. Original source
values and recipes remain in frozen v1.2. BETSI supplies family plausibility,
not inferred construction years, exact layer order, or proof of original fabric.
Climate multipliers remain neutral. TABULA and BETSI are not independent stock
observations. Original construction, transferred analogues, modern extensions,
material properties and window optics retain their explicit limitations.

A changed caller anchor/override marks its reviewed evidence unclassified and
stale. Historical payloads remain readable; the explorer displays unclassified
when evidence metadata is absent. Existing numeric lookup keys and return values
are unchanged.

## Exports and verification

V1.3 nominal exports declare construction availability and geometry-owned element
presence. Strict seven-role acceptance is versioned separately from historical
six-role institutional definitions. The core adapter no longer inserts a floor
as a basement wall. Legacy six-role callers must provide an explicit compatible
`basement_wall` construction to satisfy the current core EnvelopeSpec schema;
V1.3 has an actual basement construction.

Checks include 90 native Honeybee/core handovers, an independent nominal
resistance calculation, the complete regression suite against an isolated copy
of the candidate, and 30 seven-day January EnergyPlus export checks: five
representatives, three states, each with/without a heated basement. This is
integration verification, not annual performance, soil calibration, moisture
certification or EPC validation. EnergyPlus geometry and boundary inputs remain
caller-owned. Ground, full simulation and carbon readiness are separate flags.

## Baseline verification

The authoring, publication and historical simulation workflows are retired to the
local ignored archive. Their recorded validation describes the original release,
not a new EPC validation or a rerun during repository cleanup.

Run `python -m pytest -q` from the repository root to check the maintained
regressions and packaged dataset hashes in `BASELINE.json`. Current data live in
`src/epsm_data/datasets`; use the local `epsm-data-baseline-v1.3` Git tag to restore
the complete baseline. Do not mix datasets from different releases.

Older release payloads, integration logs and generation inputs are local archive
material. Retained reports and the original manifest are historical provenance;
paths within those records describe the layout at publication time.
