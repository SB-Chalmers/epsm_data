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
