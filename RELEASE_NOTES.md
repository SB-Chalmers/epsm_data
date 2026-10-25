# Release notes

## Unreleased — frozen LoD2 catalogue

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
- Every archetype carries an airflow-only ventilation template (S, F, FT or FTX by
  type and era; Advanced installs FTX) that epsm_core applies automatically, and
  `Catalogue.facade_assumptions()` gives window-to-wall ratios per orientation.
- Ground floors and basement walls are no longer compared with TABULA; ground heat
  transfer belongs to epsm_core / epsm_rc. See [validation](docs/validation.md)
  for the cohort coverage/match definition used by epsm_studies.
- Removed unused modules (graph visualisation, logging configuration, airflow
  conversion, duplicate thermal engine) and per-archetype snapshot tests; descriptive
  boundary notes moved to `evidence/catalogue_rationale.json`.

See [catalogue inspection](docs/catalogue-inspection.md),
[authoring](docs/archetype-authoring.md) and [sanity checks](docs/catalogue-sanity.md)
for the current interfaces. Source evidence and Git history retain the catalogue's
maintenance record.

## 0.6.0 — 15 October 2026

Unified catalogue and custom authoring, immutable editing, sourced operating
profiles and portable format-4 exchange. The library runs independently of Core
and EPSM.

## 0.5.0 — 15 October 2026

Standard Python logging for catalogue operations, with optional operation context
and explicit standalone configuration. Importing the library configures no output.
