# Frozen archetype baseline — 9 October 2026

All current EPSM Data archetypes are frozen at database **1.5.0**, construction
release **LoD2 v1.4**, package **0.3.0.dev1**. Git tag:
`epsm-data-baseline-v1.5.0`. This is a reproducible data baseline, with provisional
assumptions and validation limitations retained.

## Scope

The freeze includes all 30 canonical category/era archetypes and their 90
Existing/Standard/Advanced states, covering all 1,080 classification slots.
It also includes both source variants, for a total detailed registry of
32 archetypes and 92 states. All assemblies, material definitions, optical
assumptions, thermal targets, airflow defaults and packaged evidence are pinned
by the dataset SHA-256 manifest in [BASELINE.json](../BASELINE.json).

The manifest separately pins the dated cohort profiles and the current profile
pointer. Historical v1 profiles are retained for provenance; current assignments
use v2 and retain the parent baseline by default while support is provisional.
The [acceptance receipt](../evidence/freeze-v1.5.0.json) records catalogue coverage,
state acceptance checks and downstream readiness at the freeze.

The retained source variants are `mf_1950` (nominal target alignment remains
incomplete) and `school_fridhem` (source alignment, material mappings and
provisional construction evidence remain incomplete). They are historical
alternatives, not accepted replacements for the canonical matrix defaults.

## Values retained

No resolved thermal or infiltration value, physical layer recipe, material
property or renovation operation was changed by the freeze. MF SE.02 Existing
retains whole-window U=2.2 W/(m²K); Generic retains its historical 2.8 reference.
MF airflow keeps the provisional Atemp-based values adopted on 4 October.

Two MF SE.02 Existing target snapshots were synchronised with the catalogue's
completed 5 October validation notes (window and infiltration). Their numerical
values, sources and calculation basis were already identical. This repairs
metadata drift without retuning construction layers or weakening drift detection.
Historical release evidence remains unchanged.

## Acceptance and limits

All 1,080 slots have complete LoD1 data and seven-role canonical recipes.
Canonical LoD2 catalogue acceptance covers all 1,080 slots. This acceptance checks
recipes, source links, evidence and nominal handoff; it does not certify ground
boundaries, carbon assessment or annual simulation accuracy. Source-variant
limitations remain visible in the receipt.

The 5 October retrospective study remains provisional: baseline 54/85 buildings
within 20% error, MAE 14.302 kWh/m²/year, no fitted overrides selected. It covers
Gothenburg MF SE.02 Existing/F/district heat only. The accuracy target was not met;
other cells and independent confirmation remain pending. See
[the validation report](mf-se02-data15-validation.md).

The regression suite checks the dataset manifest, matrix coverage, independent
renovations, evidence staleness and portable nominal exports. Optional Core and
Honeybee checks require their installations. Freeze verification: **264 tests passed** in 275.36 seconds using the project
virtual environment, including explorer tests with localhost socket access. Ruff,
JavaScript syntax, Git whitespace and documentation-link checks passed. Wheel
and source distribution builds passed; wheel dataset hashes match the manifest,
and the source distribution includes documentation, profiles and the receipt.

## Working from this baseline

Start with [the explorer](../explorer/README.md), then select one archetype and
inspect its evidence and nominal export. Use `load_parametric_catalogue` for
matrix values, `load_calibrated_archetype` for physical constructions, and
`resolve_building_archetype` for evidenced building component selections.

Treat the packaged datasets as fixed inputs. Perform experiments with explicit
caller-owned catalogue/registry copies or separate workflow inputs. A future
baseline change requires a new versioned decision, evidence, checksums and freeze
record. Do not relabel this baseline or overwrite its historical evidence.

`ARCHIVE/`, runtime caches, generated simulations and the local remarks database
are outside this freeze. Runtime sources needed by fresh clones are tracked.
