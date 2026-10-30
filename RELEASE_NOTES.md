# Release notes

## Unreleased

- `heating_delivery_template("heat_pump")`: a sourced delivery template with the
  Swedish field-average seasonal COP of 2.75.
- `select_epc_comparison_terms(type, municipality_code=...)`: window airing with the
  BFS 2026:9 Fgeo table, and BEN's hot-water circulation.
- Measured-use office locators now name their evidence: operator examples in
  Sveby kontor 1.0, p. 12, not a stock survey.

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
