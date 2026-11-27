# Release notes

## 0.9.0rc2 — release candidate (27 November 2026)

A candidate for 0.9.0, for testing with EPSM 0.8.0rc2. It replaces 0.9.0rc1, which was
never published; the data values are the same, and the validation page, package metadata
and CI checks were brought up to date. Match figures for each change are
in `docs/validation.md`.

- Office SE.01 (to 1960) existing state uses the STIL2 "as found" wall U 0.70 and window
  U 2.3 of pre-1961 schools (ER 2007:11), as a proxy for offices of the same era (were 0.95
  and 2.8). Window optics, roof, ground, standard and advanced are unchanged.
- Office SE.02 (1961–1975) existing state uses the STIL2 "as found" wall U 0.40 and window
  U 1.9 of schools built 1961–75 (ER 2007:11), the same values as school SE.02, as a proxy for
  offices of the same era (were 0.60 and 2.8). Window optics, roof, ground, standard and
  advanced are unchanged. See `docs/validation.md#office-se02-existing-state-stil2-school-proxy`.
- Exhaust-air heat pumps in SE.07 (2022 onwards) use a seasonal COP of 3.0, the top of the
  Energimyndigheten 2013 floor-heating range (2.4–3.0). Current inverter units are rated
  well above that generation (NIBE S735 SCOP 4.5 at 35 °C, EN 14825). Earlier eras are
  unchanged. 3.0 is the sourced top of the range, not a fitted value.
- Single-family SE.07 FTX, as the era default and as an observed system, uses `FTX_060`
  (in-use recovery 0.60). Multi-family, office and school SE.07 keep 0.80. Field evidence
  for houses: the REHVA Journal's large-scale residential analysis (in situ about 60 % with
  leakage, defrost and imbalance), retrofitted MVHR in use at 0.65 ± 0.24, and a Swedish
  single-family house with a ground-source heat pump (Energy and Buildings 2025). Held-out
  confirmation is pending. The new optional table `observed_ftx_by_category_era` overrides
  `observed_ftx_by_era` per building type.
- School SE.01 and SE.02 existing states use the external-wall and window U-values found
  in Energimyndigheten's STIL2 school inspections (ER 2007:11): SE.01 wall 0.70 and window
  2.3 (were 1.19 and 2.8), SE.02 wall 0.40 and window 1.9 (were 0.48 and 2.7). Standard and
  advanced are unchanged. See `docs/validation.md#school-existing-state-stil2`.
- `heating_delivery_template("heat_pump", heat_pump_type=..., era=...)`: seasonal COP
  by the EPC pump type (ground 2.75, exhaust air 2.4 before 2006 and 2.75 from 2006,
  air–water 2.4, air–air 2.0). Without a pump type it is still 2.75.
  Tested on unseen single-family houses; see `docs/validation.md`.
- `epsm_data.honeybee.to_honeybee(catalogue, id, ...)` exports a configuration as a
  honeybee-energy ConstructionSet, ProgramType and IdealAirSystem, with
  `apply_to_rooms` for windows, airtightness, thermal bridges and an ISO 13370 ground
  floor. Optional extra: `pip install "epsm_data[honeybee]"`.
  Windows carry Sveby's occupant shading factor by default (0.71; schools 0.65;
  none for multi-family, as in EPSM).
  `to_honeybee(..., heat_pump_type=...)` sets `heating_cop` for the pump type and era.
- Removed unused names: `ComponentState`, `RenovationMeasureType`,
  `BuildingElement.from_name`, `ShearingLayer.sort_order` and `resolve_fractions`.

## 0.8.0 — 21 November 2026

- `heating_delivery_template("heat_pump")`: a sourced delivery template with the
  Swedish field-average seasonal COP of 2.75.
- `select_epc_comparison_terms(type, municipality_code=...)`: window airing with the
  BFS 2026:9 Fgeo table, and BEN's hot-water circulation.
- Measured-use office locators now name their evidence: operator examples in
  Sveby kontor 1.0, p. 12, not a stock survey.
- `docs/validation.md` says briefly how the catalogue was calibrated, and the
  catalogue's source locators point there.

## 0.7.0 — 29 October 2026

Data 0.7.0 is consumed by Core 0.9.0, LCA 0.3.0 and RC 0.11.0 through `epsm_data.contract`.

### Renovation catalogue

- `RenovationCatalogue.load()` reads a limited renovation catalogue (schema 2):
  25 candidates over nine measure types, independent of archetype states. Each
  candidate carries one typed payload (`LayerAddition`, `WindowSwap`,
  `SystemSwap`, `PVArray`, `DHWReduction`, `Airtightness`), its products and a
  `CostEstimate`. Licensed prices are applied from an overlay outside the package.
- `epsm_data.contract` names what Data, Core and LCA share: `QuantityDriver`,
  `Carrier`, `EndUse`, `boundary_name` and the inventory factor-reference keys.
- Products without a Boverket record carry a `CarbonReference`.
- New operations: `AirtightnessOperation`, `PVOperation`, `DHWOperation`.
- Removed: the old in-memory `RenovationCatalogue` and `Cost`; `RenovationMeasure.cost`
  is a `CostEstimate`.

See [docs/renovation-catalogue.md](docs/renovation-catalogue.md).

### Lean layout

The package is grouped by job. `from epsm_data import ...` is unchanged.

| Old module | New module |
| --- | --- |
| `library.py` | `catalogue/catalogue.py` |
| `classification.py` | `catalogue/keys.py` |
| `nominal.py` | `catalogue/handover.py` |
| `serialization.py`, `reference.py` | `catalogue/serialization.py`, `catalogue/reference.py` |
| `usecases/build_archetype.py` | `catalogue/authoring.py` |
| `catalogue.py` (renovation measures) | `renovation/measures.py` |
| `operations.py` | `renovation/operations.py` |
| `sanity.py`, `sanity_physics.py`, `sanity_reference.py`, `sanity_nonresidential.py` | `sanity/catalogue.py`, `physics.py`, `references.py`, `nonresidential.py` |
| `sources.py`, `source_cache.py` | `sources/records.py`, `sources/cache.py` |
| `carbon_scope.py` | `carbon.py` |
| `reporting/section_drawing.py` | `plotting.py` |
| `domain/building.py` | `domain/archetype.py` |
| `datasets/standards/` | `datasets/profiles/` |

`profiles.py` and `templates.py` keep their names. `facade_assumptions`,
`ventilation_template_id` and `ventilation_templates` are now exported from `epsm_data`.
Loggers are named after the package area (`epsm_data.catalogue`, `epsm_data.renovation`)
rather than the file, so moving a module no longer renames its logger.

API tidying:

- `ConstructionSet.elements` accepts a role name as well as a `BuildingElement`:
  `elements["EXT_WALL"]`.
- `envelope_u_values` keys are role names throughout; the averaged exterior wall is
  `"EXT_WALL"` (was `"wall"`).
- `Catalogue.handover(archetype_id, state=...)` exports a configuration for Core in one
  call, supplying `nominal_metadata`.
- `repr(Catalogue)` reports `archetypes=` (was `families=`), matching `summary()`.
- Docstrings now state SE.07's single configuration (`state=None`), the ventilation
  template rules per state, which measured-use inputs need an era, and the material
  identity fields.

- For one release, these old paths still import: `epsm_data.classification`,
  `library`, `nominal`, `operations`, `serialization`, and
  `epsm_data.thermal.boundary_conditions` (`get_boundary_resistances`, `get_rsi`,
  `get_rse`, now backed by `domain.element.surface_resistances`). Import from
  `epsm_data` or the new modules instead.
- Removed: the `thermal/` package, the `explorer/` web inspector, the example
  scripts (`archetype.py`, `renovations.py`, `sections.py`,
  `catalogue_composition.py`) and eleven evidence files that nothing cited.
- Examples are four notebooks, `examples/01_` to `04_`. Tests are named
  `tests/test_<area>_<topic>.py`.
- The documentation is seven pages: catalogue, authoring, profiles, sources,
  sanity, climate zones and validation.

### Frozen LoD2 catalogue

- One normalized offline catalogue: four Swedish building types, seven eras,
  76 physical configurations and 228 climate-zone assignments.
- Shared immutable materials, layers, components, elements and construction sets;
  custom authoring uses the same classes as catalogue selections.
- Portable archetype exchange, forward nominal exports, operating profiles,
  declarative renovation definitions and offline climate-zone lookup.
- Forward sanity checks report thermal, carbon, operation and reference coverage
  separately, with affected catalogue assignments.
- School and office definitions distinguish basement ceilings from soil slabs,
  cold-attic ceilings from weather roofs, and reciprocal intermediate-floor order.
- Source mappings include explicit external carbon references. The retained sand
  proxy has a production factor and unknown A4/A5 modules, which remain visible.
- Every thermal grade is an EPSM record with structured provenance (Swedish
  product declarations, design values, TABULA grades or derivations); the bundled
  Honeybee libraries are removed. Unsourced renovation grades block readiness.
- TABULA-covered windows match TABULA exactly; window optics derive from glazing
  g and light transmittance with a 0.30 frame fraction.
- Resolved payloads use a `thermal` section and `thermal_id`. Older `honeybee` /
  `honeybee_id` payloads still load, `Catalogue.honeybee_materials` remains an
  alias and nominal references carry both ids.
- Every archetype can use any ventilation system: `get(..., ventilation="S"|"F"|"FT"|"FTX")`
  selects the template for a building's observed (EPC) system, with an era default
  when unknown; Advanced installs FTX 0.80. epsm_core applies it automatically, and
  `Catalogue.facade_assumptions()` gives window-to-wall ratios per orientation.
- Ground floors and basement walls are no longer compared with TABULA; ground heat
  transfer belongs to epsm_core / epsm_rc. See [validation](docs/validation.md)
  for the cohort coverage/match definition used by epsm_studies.
- Removed unused modules (graph visualisation, logging configuration, airflow
  conversion, duplicate thermal engine) and per-archetype snapshot tests.

See [catalogue](docs/catalogue.md), [authoring](docs/authoring.md) and
[sanity checks](docs/sanity.md) for the current interfaces.

## 0.6.0 — 15 October 2026

Unified catalogue and custom authoring, immutable editing, sourced operating
profiles and portable format-4 exchange. The library runs independently of Core
and EPSM.

## 0.5.0 — 15 October 2026

Standard Python logging for catalogue operations, with optional operation context
and explicit standalone configuration. Importing the library configures no output.
