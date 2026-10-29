# Renovation catalogue

A deliberately limited catalogue of renovation **candidates**: what a measure
installs, never where, how much or at what impact.

## Who owns what

| Package | Owns | Never does |
|---|---|---|
| `epsm_data` | Measure types, candidates (components, window records, ventilation templates, products), duct-layout assumptions, cost-estimate *structure* | Choose targets, compute quantities, totals or impacts |
| `epsm_core` | Target selection, geometric quantity drivers, application through `Building.renovate` (the single renovation path), installations, material flows | Read prices or climate factors |
| `epsm_lca` | Carbon of installed/removed quantities (Boverket), cost = rate × driver per stage | Load catalogues or change buildings |

`Building.renovate` alone enforces measure prerequisites and incompatibilities.

## Independent of archetype renovation states

`standard` and `advanced` archetype states describe buildings that were
renovated **before** they entered the stock. They are baselines, not outcomes of
this catalogue. The catalogue holds no packages per state, and its readiness check
never compares against them. Candidates only reuse the shared LoD2 physical
library (components and window records).

## Payloads and the shared contract

A candidate is a small record (identity, sources, service life, cost, products,
companions) holding one typed **payload** that says what it installs:

| Payload | Measure types | Core resolver |
|---|---|---|
| `LayerAddition` | insulate wall / roof / basement | targets, element areas |
| `WindowSwap` | replace / upgrade window | targets, window area and count |
| `SystemSwap` | upgrade ventilation | airflow, units, risers, terminals, ducts |
| `PVArray` | install PV | roof area and peak power |
| `DHWReduction` | reduce DHW | floor area |
| `Airtightness` | seal envelope | renovated envelope share (an effect) |

The measure type fixes the payload class, the allowed roles and the defaults
(placement side, retained window unit). Payloads are registered in `PAYLOADS`.
Core has one resolver per payload (`epsm_core.measures.RESOLVERS`) and one applier
per Data operation (`epsm_core.renovation_apply.APPLIERS`). `Building.renovate`
works on `ResolvedMeasure` records only. Adding a type means one payload class and
one resolver.

Names shared by the three packages live in `epsm_data.contract`:

- `QuantityDriver` for cost and product drivers;
- `Carrier` and `EndUse`, with `boundary_name` for energy;
- the factor-reference keys of installed products.

Stage quantities keep priced `drivers` apart from descriptive `effects`.

## Measure types

| Type | Roles | Action | Placement |
|---|---|---|---|
| `insulate_wall` | EXT_WALL | add components | exterior (interior candidates override) |
| `insulate_roof` | TOP_FLOOR (cold attic), ROOF (compact) | add components | exterior / cold side |
| `insulate_basement` | BASEMENT_WALL, GROUND_FLOOR | add components | interior / warm side; ceiling over an unheated basement on its underside |
| `replace_window` | WINDOW | replace element; old unit removed | – |
| `upgrade_window` | WINDOW | replace element; unit retained, glazing installed as a product | – |
| `upgrade_ventilation` | – | replace HVAC template; ducts, units and terminals installed as products | – |
| `install_pv` | – | add a roof PV array sized from roof area | – |
| `reduce_dhw` | – | reduce hot-water use; fittings installed as products | – |
| `seal_envelope` | – | reduce infiltration; dependent on a host, priced with it | – |

Default targets are the thermal envelope only: elements with an `Outdoors` or
`Ground` boundary. Party walls and internal floors keep their construction. A
candidate may name other `target_boundaries`: attic floors under a cold attic are
`Internal`, and the ceiling over an unheated basement is the `Internal` ground
floor (core refuses it when the basement is heated). `side` overrides the type's
placement, for interior wall linings.

Candidates may install renovation-only materials, layers and components defined in
the renovation dataset, such as cellulose and wood-fibre loose fill (Boverket
6000000137 / 6000000135) and wood-fibre batts (6000000136). The LoD2 library is
not changed.

## Sealing: a dependent measure

`seal_envelope` stands for the airtightness gained when the envelope is opened
and rebuilt. Its hosts are `replace_window` and `insulate_wall`; those candidates
list it in `companions`. Sealing is still a measure of its own: it has its own
candidate, effect, stage entry and log record, but:

- it is never applied by itself; without a host in the same stage, core raises;
- `apply_candidates` adds it automatically after its hosts (`companions=False` opts out);
- it adds no products or cost, because sealant and tape are inside the host's work item
  (`priced_with_host`);
- its effect is a nominal default (`infiltration_reduction`, 20 % for a fully
  renovated envelope), scaled by the share of outdoor envelope area its hosts
  renovated. Core logs `renovation.sealing.default_applied` every time.

## Candidate record

`datasets/renovation/catalogue.json` (schema 2, payloads), written by
`tools/build_renovation_catalogue.py`:

- `candidate_id`, `measure_type`, `name`, `description`, `role`
- what is installed: `component_ids` (outside → inside), `window_id`, or
  `template_id` + `airflow` overrides
- applicability: `roof_topologies`, `from_ventilation`
- dependencies: `companions` (host side), `infiltration_reduction` (sealing side)
- `performance` (declared, for checking), `service_life_years`
- `products`: items outside the layered envelope, each with a quantity
  `driver`, `unit` (item, m, m2), `mass_kg_per_unit` and `boverket_id`
- `layout` (ventilation only): design airflow, terminal densities, branch and
  main duct lengths, riser spacing, unit size, and the duct networks and terminals
  that are new for each existing system (S, F, FT, FTX)
- `cost`: a `CostEstimate`, normally supplied by an overlay (see below)

## PV

`install_pv` sizes one array per building: 80 % of the footprint on flat roofs,
30 % of the actual roof surface on pitched roofs, at 130 W per m2 of roof used,
due south, 15° tilt, 12 % system losses. Core appends a `PVSpec` to the
building's renewables. Carbon: mono-Si modules from Boverket 6000000203 (per m2 of
module at 209 W/m2) plus 460 kg CO2e/kWp for inverter and mounting derived from
IEA PVPS Task 12 (2023). Cost: 12,100 SEK/kWp excl. VAT (IEA PVPS NSR Sweden
2024, 10–100 kW), split by the published villa cost structure.

## Low-flow DHW

`reduce_dhw` lowers `dhw_kwh_m2_year` by 25 % (RISE/E2B2 measured 28 %) in the
operation profile and in zone use overrides. Cost 90 SEK/m2 Atemp (SBUF 11488,
2009, escalated by an assumed 45 %); carbon 0.2 kg CO2e/m2 A1–A3 from mixer EPDs.
Products without a Boverket record carry a `CarbonReference` stated per the
product's unit, with its source URL and method; undeclared modules (here A4 and
A5) are explicit unknowns. Core passes the reference with each installation and
LCA reads it like any other external declaration.

## Cost attribute

```
CostEstimate(currency, price_year, items, coverage="complete"|"partial",
             missing_scope, includes_vat=False, source_references, notes)
CostItem(category: material|labour|subcontractor|overhead,
         rate per driver unit, driver, labour_hours per driver unit, source)
```

Drivers are the quantities Core resolves: `element_area_m2`, `window_area_m2`,
`window_count`, `floor_area_m2`, `airflow_l_s`, `duct_length_m`,
`supply_terminal_count`, `exhaust_terminal_count`, `ahu_count`, `riser_count`,
`building`. An estimate marked partial must name what it does not price. LCA then
reports the priced subtotal but leaves the total open.

The bundled dataset carries only publicly sourced prices (PV, DHW). Licensed price books belong in an overlay
outside the repository. Overlay keys are a candidate ID, `<measure_type>/<role>`
or `<measure_type>`, and the most specific key wins:

```python
renovations = RenovationCatalogue.load(Catalogue.load(), costs="private/costs.json")
```

`tools/wikells_cost_overlay.py EXPORT.xlsx OUT.json` builds such an overlay from a
Wikells Sektionsdata export. It records which work item prices which measure.

## Ventilation quantities (Core)

For each conditioned part, with a conditioned basement counted as a storey:

- airflow = `mechanical_vent_l_s_m2` × floor area
- units = ⌈airflow / `ahu_max_airflow_l_s`⌉
- risers = ⌈footprint / `riser_area_m2`⌉
- duct length = new networks × Σ(risers × height + storeys × footprint ×
  `main_duct_m_per_m2`) + new terminals × `branch_length_m`

Existing networks are retained. S → FTX adds two networks and both terminal kinds;
F → FTX adds the supply network and supply terminals.

## Readiness

`RenovationCatalogue.readiness(library)` checks every measure type against every
archetype's current construction (Existing, or the single default state). It
reports candidate counts, priced and fully priced counts, archetypes without an
installable candidate, and any operation that fails to apply.

## Known gaps

- Upgrade-window U 1.3, the glazed share, the ventilation layout, and the
  AHU/terminal masses (galvanised-steel proxies) are EPSM assumptions to calibrate.
- Service lives are placeholders; B4 replacement is not assessed yet.
- Materials whose carbon comes from an EPD reference (for example the loose
  glass wool) need external-carbon support in `epsm_lca`.
- Price books seen so far do not price air handling units, ductwork or window
  glazing retrofits.
