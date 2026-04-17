# BETSI Multifamily Building Data — Reference & Archetype Guide

Source: `BETSI/` (this directory; scripts use `Path(__file__).parent`)  
Encoding: `latin-1`, separator: `;`, decimal: `,`  
Filename encoding is broken (ä→„, ö→", å→†) — use `glob.glob()` to find files.

---

## 1. Scope

BETSI (Byggnaders Energi, Status och Tillstånd Inventering) surveyed **559 FH (flerbostadshus / multifamily)** buildings across Sweden circa 2007–2008. Each building was inspected on-site with layer-by-layer envelope measurements.

---

## 2. File Inventory

### Layer-level construction data (SelectKod / SelectLambda / SelectTjocklek / R)

| File | Component | FH Buildings | Rows/bldg | Notes |
|---|---|---|---|---|
| `FB52 Yttervägg.csv` | Ext wall layers | 559 (100%) | 1–9 | Joined with FB49 for U, area, facade |
| `FB49 Yttervägg.csv` | Ext wall summary | 559 (100%) | 1–3 walls | U-value, area, facade material |
| `FB56 Vindsbjl.csv` | Attic floor / horizontal roof | 545 (97.5%) | 1–6 | Most common roof insulation boundary |
| `FB62 Snedtak.csv` | Sloped roof (insulated in rafters) | 94 (16.8%) | 1–6 | 89 buildings have BOTH FB56+FB62 |
| `FB33 Kryp PPM.csv` | Ground floor (slab on grade / basement floor) | 537 (96.1%) | 1–6 | Primary floor component |
| `FB30 Kryp Bjl.csv` | Crawl space floor | 40 (7.2%) | 1–3 | Only for buildings with crawl space |
| `FB40 Källare.csv` | Basement slab (unheated) | 27 (4.8%) | 1–5 | Column prefix is FB41* |
| `FB47 Källarvägg.csv` | Basement wall | 361 (64.6%) | 1–5 | |
| `FB59 Stödbensvägg.csv` | Knee wall | 64 (11.4%) | 1–4 | Only for buildings with attic rooms |

### Window data (U-value, area, frame type — per orientation)

| File | Orientation | FH Buildings |
|---|---|---|
| `FB87 Fönster O.csv` | East | 516 (92.3%) |
| `FB88 Fönster N.csv` | North | 511 (91.4%) |
| `FB91 Fönster S.csv` | South | 519 (92.8%) |
| `FB94 Fönster V.csv` | West | 513 (91.8%) |

Window columns: `Fönstertyp` (e.g. "3-glas isolerruta"), `Uvärde`, `Fönsterarea`, `Karmmaterial` (e.g. "Träfönster").

### Metadata

| File | Key columns | Notes |
|---|---|---|
| `FA.csv` | `FA11Byggnadstyp`, areas, floors, orientation | Building type, geometry |
| `FB_OVRIGT.csv` | `FB5 Vertikalt bärverk`, `FB1 Produktionsmetod`, `FB4 Material mellanbjälklag`, `FB69 Takform` | Structural system, roof form |
| `FB_Klimat.csv` | Summary U/UA values, areas, all component summaries | Pre-computed thermal totals |
| `FC3.csv` | 19 renovation year columns | Earliest renovation as age sanity check |
| `FX.csv` | `FXByggår` | Construction year — **SH only, 0 FH rows** |

### Not useful for archetypes

| File | Why |
|---|---|
| `FC1/FC2 *.csv` | Condition assessments — 0 FH rows |
| `FD/FE/FF/FG/FH.csv` | Indoor environment, occupant surveys |
| `Uppräkningstal.csv` | Sampling weights — SH only |
| `RADON/LUFTKVALITET.csv` | Air quality measurements |

---

## 3. Core Envelope Coverage

**550 / 559 buildings (98.4%)** have all four core components:

```
EXT_WALL (FB52)          559  100%
ROOF (FB56 or FB62)      550   98%
FLOOR (FB33/30/40)       559  100%
WINDOWS (any FB87-94)    559  100%
```

The 9 missing buildings lack roof data only.

---

## 4. Construction Year

**No direct construction year exists for FH buildings.** `FXByggår` and `ald` age bands are SH-only.

### Proxy: Structural system → estimated era

From `FB_OVRIGT.csv` column `FB5 Vertikalt bärverk`:

| Swedish value | English | EstimatedEra | Count |
|---|---|---|---|
| Väggar av betong | Concrete walls | 1950–1975 | 247 |
| Alla väggar av betong | All-concrete walls | 1960–1980 | 112 |
| Murverk | Masonry | pre-1960 | 74 |
| Träregelstomme | Timber frame | mixed | 57 |
| Annat, vilken? | Other | — | 27 |
| Vet inte | Unknown | — | 15 |
| Kombination | Combination | mixed | 14 |
| Pelare av betong | Concrete columns | 1960–1980 | 8 |

### Sanity check: FC3 renovation years

284 / 559 buildings have at least one renovation year. Cross-referencing confirms all earliest renovation dates fall after the estimated era lower bound (no contradictions).

| EstimatedEra | n | min renov | median | max |
|---|---|---|---|---|
| pre-1960 | 55 | 1970 | 1990 | 2007 |
| 1950-1975 | 118 | 1970 | 2000 | 2007 |
| 1960-1980 | 63 | 1980 | 1999 | 2007 |
| mixed | 21 | 1960 | 1998 | 2006 |

---

## 5. Material System

All layer files use the same coded material system. **34 unique codes** appear, of which 30 are defined (1–30) and 4 are data artifacts (0, 31, 32, 99).

### Material code → name → lambda

BETSI assigns a fixed lambda per material code. The lambda is stored per row in `SelectLambda`.

| Code | Material | Typical k (W/mK) |
|---|---|---|
| 1 | Mineral wool boards | 0.036–0.045 |
| 2 | Brick | 0.6–1.2 |
| 3 | Calcium silicate | 0.07 |
| 4 | Leca block | 0.2–0.3 |
| 5 | Cellular plastic XPS/EPS | 0.033–0.040 |
| 6 | Mineral wool loose | 0.040–0.050 |
| 7 | Wood shavings/sawdust | 0.06–0.08 |
| 8 | Wood | 0.13–0.22 |
| 9 | Aerated concrete | 0.12–0.18 |
| 10 | Concrete | 1.2–2.3 |
| 11 | Cork | 0.04 |
| 12 | Glass | ~1.0 |
| 13 | Steel | ~50 |
| 14 | Lightweight aggregate block | 0.2–0.6 |
| 15 | Lightweight concrete (cast) | 0.2–0.6 |
| 16 | Cellular glass/foam glass | 0.04 |
| 17 | Polyurethane foam | 0.025 |
| 18 | Asphalt board/felt | 0.17–0.23 |
| 19 | Mineral wool (older) | 0.040–0.050 |
| 20 | Mineral wool (modern) | 0.035–0.040 |
| 21 | Air gap | — |
| 22 | Gypsum board | 0.16 |
| 23 | Plaster/render | 0.7–1.0 |
| 24 | Plywood/fibreboard | 0.07–0.14 |
| 25 | Plastic foil | — (negligible) |
| 26 | Window | — (not opaque) |
| 27 | Lightweight concrete block | 0.3–0.6 |
| 28 | Timber frame+insulation | 0.05–0.08 (effective) |
| 29 | Other | varies |
| 30 | Insulation board (other) | varies |

### Mapping to our EP/Honeybee materials

**18 / 30 already mapped** in `Data/Material_Database.xlsx`:

| BETSI code | Our material name | EP identifier |
|---|---|---|
| 1, 6, 19, 20 | mineral_wool | Wall Insulation [31] / AtticFloor Insulation |
| 2 | brick | M01 100mm brick |
| 4, 14 | leca | Leca (created) |
| 5 | cellular_plastic | ⚠ Currently → Roof Membrane (WRONG k=0.16, needs fix → k=0.035) |
| 7 | wood_shavings | Wood Shavings (created) |
| 8 | wood | Std Wood 6 in. |
| 10 | concrete | 100mm Normalweight concrete floor |
| 15, 27 | lightweight_concrete | M11 100mm lightweight concrete |
| 18 | asphalt_board | Asphalt Board (created) |
| 22 | gypsum_board | 5/8 in. Gypsum Board |
| 23 | plaster | 1IN Stucco / 25mm Stucco |
| 24 | wood_fiber_board | Woodfiber Board (created) |

**7 need new EP material entries:**

| BETSI code | Material | Suggested k | Action |
|---|---|---|---|
| 3 | Calcium silicate board | 0.07 | Create custom entry |
| 11 | Cork insulation | 0.04 | Create custom entry |
| 13 | Steel | 50 | Reuse existing `F08 Metal surface` |
| 16 | Cellular glass / foam glass | 0.04 | Create custom entry |
| 17 | Polyurethane foam (PUR) | 0.025 | Create custom entry |
| 28 | Timber frame+insulation | 0.06 | Create composite effective entry |
| 30 | Insulation board (other) | 0.04 | Create generic entry |

**Skip (not real opaque materials):** 0, 21, 25, 26, 29, 31, 32, 99

### EP Material Conductivity Audit

Full audit (`debug_material_audit.py`) comparing all Excel materials against EP/Honeybee JSON properties. **6 issues found:**

| Our material | EP identifier | EP k | Expected k | Issue |
|---|---|---|---|---|
| cellular_plastic | Roof Membrane | 0.160 | 0.033–0.040 | **WRONG match** — k is ~4× too high. Mapped to generic roof membrane instead of XPS/EPS. |
| lightweight_concrete | M11 100mm lightweight concrete | 0.530 | *(correct for lättbetong)* | ⚠ Expected-range in audit script was wrong (used concrete range 1.0–2.5); actual EP k=0.53 is correct for lightweight concrete. |
| concrete_mixed_with_sawdust | Cement Bonded Particleboard (created) | 0.230 | 1.0–2.5 | Low confidence match (3). k=0.23 may be reasonable for this composite — verify. |
| woodfiber_board | Woodfiber Board (created) | 0.070 | 0.07–0.14 | Borderline — k=0.07 is at the low end. Reasonable for soft fibreboard (träfiberskiva). |
| wood_shavings | Wood Shavings (created) | 0.062 | 0.06–0.08 | OK — within BETSI range. Audit expected wrong range (0.10–0.18 = solid wood). |
| gravel | Solid Rock | 3.000 | 0.5–2.5 | Mapped to solid rock instead of loose gravel. Not used in current archetypes. |

**Suspicious "Roof Membrane" cluster** — 8 materials all map to the same EP entry (Roof Membrane, k=0.1599, ρ=1121.3):
`cellular_plastic`, `foil`, `vinyl_flooring`, `plastic_mat`, `linoleum`, `roofing_felt`, `membrane`, `waterproof_membrane`, `paper`.
Only `roofing_felt` and `membrane`/`waterproof_membrane` are correct matches. The others need dedicated EP entries or remapping.

**Critical fix needed:** `cellular_plastic` → create/use proper XPS/EPS material (k≈0.035, ρ≈30). This affects any archetype using EPS/XPS insulation (e.g. ground floor slab insulation).

---

## 6. Intermediate Floors & Roof Forms

**Intermediate floors:** No layer data — only a single `FB4 Material i mellanbjälklag` value (Betong 471, Trä 67, Lättbetong 8). Not part of thermal envelope.

**Roof forms** from `FB69 Takform`:

| Form | Count | Thermal data in |
|---|---|---|
| Sadeltak (gable) | 357 | FB56 |
| Motfallstak (counter-pitch) | 52 | FB56 |
| Valmat sadeltak (hipped) | 50 | FB56 |
| Pulpettak (mono-pitch) | 44 | FB56 |
| Horisontaltak (flat) | 28 | FB56 |
| Mansardtak (mansard) | 19 | FB56+FB62 |

The thermal boundary is always in FB56 (attic floor slab) or FB62 (sloped roof rafters), regardless of roof shape.

---

## 7. Building Metadata

### Building type (`FA11Byggnadstyp`)

| Swedish | English | Count |
|---|---|---|
| Lamellhus | Slab block | 212 |
| Skivhus | Tower slab | 123 |
| Punkthus | Point block | 78 |
| Loftgångshus | Gallery access | 49 |
| Flerbostadsvilla | Multi-family villa | 43 |
| AnnanVilken | Other | 39 |
| Radhus | Terraced house | 14 |

### Production method (`FB1 Produktionsmetod bärande väggar`)

| Value | Count |
|---|---|
| PlatsbyggdaVäggar (site-built) | 437 |
| PrefabriceradeVäggar (prefabricated) | 95 |
| VetInte (unknown) | 27 |

### Foundation type (`FB_Klimat.FB31/FB32`)

Most buildings have a `Platta på mark` (slab on grade) or `Källare` (basement). Check `FB_Klimat.csv` for area and U-value summaries per foundation type.

---

## 8. Pre-Computed Thermal Summary

`FB_Klimat.csv` contains per-building totals — useful for validation:

- `Totalt UA-värde` / `Totalt UA-värde inkl köldbryggor` — total envelope UA
- `U-medelvärde` / `U-medelvärde inkl köldbryggor` — average U
- `Total omslutningsarea` — total envelope area
- `Total ytterväggsarea`, `Total fönsterarea`
- Per-component: `FB52 UA-värde ytterväggar`, `FB56 UA-värde vindsbjälklag`, etc.

---

## 9. Strategy for Building Archetypes

### Option A: Per-building archetypes (559 individual)

Each building becomes its own archetype. Directly assemble layers from the FB files.

**Pipeline:**
1. For each building ID (`FH1001`–`FH1559`):
   - Read layers from FB52 (wall), FB56/62 (roof), FB33/30/40 (floor), FB47 (basement wall)
   - Map `SelectKod` → EP material using the mapping table above
   - Use `SelectTjocklek` (mm → m) for thickness
   - Read window U + area from FB87/88/91/94
   - Pull metadata from FA (type, floors, areas) and FB_OVRIGT (structural system, production)
2. Compute U-values from layer stacks (SS-EN ISO 6946)
3. Validate against `FB_Klimat.csv` pre-computed U and UA values

**Pros:** Maximum fidelity, no averaging.  
**Cons:** 559 archetypes is large; some will be very similar.

### Option B: Era-clustered archetypes (matching CMF scheme)

Group buildings by EstimatedEra and average their constructions.

**Suggested clusters:**

| Cluster | Era | Structural system | Expected count |
|---|---|---|---|
| CMF_pre1945 | pre-1960 | Masonry | ~74 |
| CMF_1945_1960 | pre-1960 | Masonry (post-war) | subset |
| CMF_1960_1975 | 1950-1975 | Concrete walls | ~247 |
| CMF_1975_1985 | 1960-1980 | All-concrete/prefab | ~123 |
| CMF_1985_2005 | mixed/post-1990 | Timber frame + newer | ~71 |

**Pipeline:**
1. Assign each building to a cluster using EstimatedEra + BuildingType
2. For each cluster, compute median layer thicknesses and material frequencies
3. Build a representative construction by taking the most common material per layer position
4. Compute representative U-values

### Option C: Hybrid — use BETSI to validate/fill EPSM archetypes

Use BETSI statistics to:
- Add missing insulation layers to CMF_1940/1950/1970/1980 ext walls
- Cross-check U-values against BETSI medians per era
- Fill in TABULA gaps with BETSI empirical data

---

## 10. Key Caveats

1. **No construction year for FH** — era estimates are proxies from structural system. Some buildings may be mis-classified.
2. **Code 28 (timber frame+insulation)** is a composite — the surveyor recorded an effective conductivity for the whole stud wall, not separate layers.
3. **Codes 0, 31, 32, 99** are undocumented. Rows with these codes should be flagged or excluded.
4. **BETSI lambdas may differ from EP values** — BETSI uses field-estimated conductivities, while EP uses lab-certified values. Always prefer the BETSI lambda for thermal calculations and map to EP materials for identification only.
5. **Window data is U-value only** — no layer construction. Use directly as window U-values per orientation.
6. **FB_Klimat includes thermal bridge corrections** (`inkl köldbryggor`) — these add ~15-20% to UA values.

---

## 11. Combined CSV Output

All combine scripts use `_betsi_common.py` for shared metadata (material names, structural system mappings, building metadata loading). Each script reads its component-specific BETSI CSV files, joins with building metadata, and writes a combined CSV to the `BETSI/` directory.

**Usage:** `python BETSI/debug_betsi_<component>.py`

### 11.1 Exterior Walls

`BETSI/betsi_ext_walls_combined.csv` — 2075 rows, 559 buildings.

| Column | Description |
|---|---|
| Byggnad | Building ID (FH1001–FH1559) |
| BuildingType, ProductionMethod, StructuralSystem, EstimatedEra, EarliestRenovation | Metadata |
| WallNr, FacadeMaterial | Wall variant and facade finish |
| U_value_W_m2K, TotalThickness_mm, TotalR_m2K_W | Wall-level thermal summary |
| WallArea_m2, WallPercent | Wall area and share |
| MaterialCode, Material, Lambda_W_mK, Thickness_mm, R_m2K_W | Per-layer construction |

Generated by `debug_betsi_walls.py`. Source: FB49 + FB52.

### 11.2 Ground Floors

`BETSI/betsi_ground_floors_combined.csv` — 1139 rows, 537 buildings.

| Column | Description |
|---|---|
| Byggnad, BuildingType, …, EstimatedEra, EarliestRenovation | Metadata |
| FloorType | Slab on grade / Basement floor |
| U_value_W_m2K, TotalThickness_mm, TotalR_m2K_W, FloorArea_m2 | Floor-level thermal summary |
| MaterialCode, Material, Lambda_W_mK, Thickness_mm, R_m2K_W | Per-layer construction |

Generated by `debug_betsi_floors.py`. Source: FB33 + FB_Klimat.

### 11.3 Roofs

`BETSI/betsi_roofs_combined.csv` — 1405 rows, 550 buildings.

| Column | Description |
|---|---|
| Byggnad, BuildingType, …, EstimatedEra, EarliestRenovation | Metadata |
| RoofType | Attic floor (horizontal) / Sloped roof (rafters) |
| U_value_W_m2K, TotalThickness_mm, TotalR_m2K_W, RoofArea_m2 | Roof-level thermal summary |
| MaterialCode, Material, Lambda_W_mK, Thickness_mm, R_m2K_W | Per-layer construction |

Generated by `debug_betsi_roofs.py`. Source: FB56 + FB62 + FB_Klimat.

### 11.4 Windows

`BETSI/betsi_windows_combined.csv` — 2125 rows, 559 buildings.

| Column | Description |
|---|---|
| Byggnad, BuildingType, …, EstimatedEra, EarliestRenovation | Metadata |
| Orientation | East / North / South / West |
| WindowType | e.g. "3-glas isolerruta" |
| U_value_W_m2K, WindowArea_m2, FrameMaterial | Per-orientation window data |

Generated by `debug_betsi_windows.py`. Source: FB87/88/91/94.

### 11.5 Basement Walls

`BETSI/betsi_basement_walls_combined.csv` — 692 rows, 361 buildings.

| Column | Description |
|---|---|
| Byggnad, BuildingType, …, EstimatedEra, EarliestRenovation | Metadata |
| U_value_below_grade_W_m2K, U_value_above_grade_W_m2K | Separate U-values |
| TotalThickness_mm, TotalR_m2K_W | Wall-level summary |
| WallArea_below_grade_m2, WallArea_above_grade_m2 | Areas |
| MaterialCode, Material, Lambda_W_mK, Thickness_mm, R_m2K_W | Per-layer construction |

Generated by `debug_betsi_basement_walls.py`. Source: FB47 + FB_Klimat.

### 11.6 Basement Floors

`BETSI/betsi_basement_floors_combined.csv` — 62 rows, 27 buildings.

| Column | Description |
|---|---|
| Byggnad, BuildingType, …, EstimatedEra, EarliestRenovation | Metadata |
| HasBasement, BasementHeated | Basement status |
| U_value_W_m2K, TotalThickness_mm, TotalR_m2K_W, FloorArea_m2 | Floor-level thermal summary |
| MaterialCode, Material, Lambda_W_mK, Thickness_mm, R_m2K_W | Per-layer construction |

Generated by `debug_betsi_basement_floors.py`. Source: FB40 + FB_Klimat.

### 11.7 Crawl Space Floors

`BETSI/betsi_crawl_space_floors_combined.csv` — 82 rows, 40 buildings.

| Column | Description |
|---|---|
| Byggnad, BuildingType, …, EstimatedEra, EarliestRenovation | Metadata |
| U_value_W_m2K, TotalThickness_mm, TotalR_m2K_W, FloorArea_m2 | Floor-level thermal summary |
| MaterialCode, Material, Lambda_W_mK, Thickness_mm, R_m2K_W | Per-layer construction |

Generated by `debug_betsi_crawl_space.py`. Source: FB30 + FB_Klimat.

### 11.8 Knee Walls

`BETSI/betsi_knee_walls_combined.csv` — 133 rows, 64 buildings.

| Column | Description |
|---|---|
| Byggnad, BuildingType, …, EstimatedEra, EarliestRenovation | Metadata |
| U_value_W_m2K, TotalThickness_mm, TotalR_m2K_W, WallArea_m2 | Wall-level thermal summary |
| MaterialCode, Material, Lambda_W_mK, Thickness_mm, R_m2K_W | Per-layer construction |

Generated by `debug_betsi_knee_walls.py`. Source: FB59 + FB_Klimat.

---

## 12. National-Level Validation Data (from Boverket Report)

Source: *Teknisk status i den svenska bebyggelsen – resultat från projektet BETSI*, Boverket 2010 (`BETSI_teknisk_status.md`).
This report provides **population-level statistics** (with 95% confidence intervals) that can validate our per-building archetypes. All data below is for **flerbostadshus** unless noted.

### 12.1 The "Average" Flerbostadshus

| Property | Value |
|---|---|
| Average year built | 1959 |
| Stories | Basement + 3 above ground |
| Facade | Brick (tegel) or render (puts) |
| Roof | Saddleback with concrete tiles |
| Atemp | 1,426 m² |
| Exterior wall U-value | 0.411 W/(m²·K) |
| Apartments per building | 14.55 |
| Persons per apartment | 1.7 |

### 12.2 Building Stock Size

| Age class | Buildings (×10³) | Apartments (×10³) | Volume (10⁶ m³) | Atemp (10⁶ m²) |
|---|---|---|---|---|
| –1960 | 77 | 1,031 | 247 | 98.5 ± 18.6 |
| 1961–75 | 32 | 768 | 185 | 75.6 ± 16.6 |
| 1976–85 | 12 | 130 | 35 | 14.3 ± 2.9 |
| 1986–95 | 31 | 364 | 95 | 37.8 ± 14.9 |
| 1996–05 | 12 | 102 | 28 | 11.5 ± 5.2 |
| **Total** | **~165** | **~2,396** | **588** | **237.7 ± 38.8** |

---

## 13. Component-Level U-Values for Validation

Use these to validate computed U-values from BETSI layer data. Values are population-weighted means ± 95% CI.

### 13.1 Exterior Walls (Ytterväggar)

| Age class | U-value W/(m²·K) | ELIB comparison |
|---|---|---|
| –1960 | **0.58 ± 0.07** | Improved since ELIB |
| 1961–75 | **0.41 ± 0.07** | Improved since ELIB |
| 1976–85 | **0.33 ± 0.17** | Large CI — heterogeneous stock |
| 1986–95 | **0.22 ± 0.03** | |
| 1996–05 | **0.20 ± 0.05** | |
| **Total** | **0.44 ± 0.05** | |

- Average total stock: 0.41 W/(m²·K) (per-building-type value from report text; matches `FB_Klimat` median).
- To bring oldest walls to newest standard requires **~190 mm additional mineral wool**.

### 13.2 Horizontal Attic Floor (Vindsbjälklag)

| Age class | U-value W/(m²·K) |
|---|---|
| –1960 | **0.36 ± 0.07** |
| 1961–75 | **0.20 ± 0.04** |
| 1976–85 | **0.17 ± 0.02** |
| 1986–95 | **0.15 ± 0.04** |
| 1996–05 | **0.13 ± 0.04** |
| **Total** | **0.24 ± 0.04** |

- To bring oldest to newest requires **~250 mm additional loose-fill insulation**.
- 68% of FH can have vindsbjälklag additionally insulated without cultural-historical concern; 15% cannot, 17% uncertain.

### 13.3 Windows (Fönster)

| Age class | U-value W/(m²·K) |
|---|---|
| –1960 | **2.2 ± 0.07** |
| 1961–75 | **2.2 ± 0.08** |
| 1976–85 | **2.0 ± 0.09** |
| 1986–95 | **1.8 ± 0.21** |
| 1996–05 | **2.0 ± 0.07** |
| **Total** | **2.1 ± 0.07** |

- **Caveat:** Surprisingly small variation across ages. Many older windows have been replaced. Low-e coatings were hard to detect in field inspections.
- If all windows were replaced with modern energy-efficient ones, average U-value could drop to **< 1.0 W/(m²·K)**.

### 13.4 Ground Floor / Slab on Grade (Platta på mark / Källargolv)

**Not published** in the Boverket report. Values below are computed from BETSI raw layer data (FB33, 537 FH buildings). See `output/betsi_ground_floors_combined.csv`.

| EstimatedEra | n | Mean U | Median U | Std | Q25 | Q75 |
|---|---|---|---|---|---|---|
| pre-1960 | 71 | **0.345** | **0.314** | 0.119 | 0.264 | 0.430 |
| 1950–1975 | 235 | **0.291** | **0.266** | 0.134 | 0.190 | 0.372 |
| 1960–1980 | 113 | **0.263** | **0.230** | 0.120 | 0.179 | 0.299 |
| mixed | 60 | **0.319** | **0.240** | 0.199 | 0.184 | 0.409 |
| (unmapped) | 39 | 0.286 | 0.292 | 0.111 | 0.190 | 0.365 |

- **TABULA reference** for 1961–75: U = 0.26 — matches the BETSI median (0.266) well.
- Note: BETSI era assignment is by structural system proxy, not actual construction year.
- Ground floors have high variance — `pre-1960` ranges from 0.13 to 0.69. Some have insulation (cellular plastic or mineral wool under slab), many do not.

### 13.5 Unrenovated vs Renovated U-Values

The population means in §13.1–13.4 blend renovated and unrenovated buildings. Splitting by **component-specific** FC3 renovation status reveals large differences, especially for pre-1960 stock.

Source: `debug_uvalue_by_renovation.py` — uses FC3 columns: `FC3 Byte fasad år` / `FC3 Tilläggsisolering fasad år` (walls), `FC3 Tilläggsisolering vind år` (roof), `FC3 Fönster år` (windows). Ground floor has no component-specific column — uses `any_renovated` as proxy.

#### Renovation counts

| Component | Buildings renovated | Share |
|---|---|---|
| Ext wall (facade replacement or insulation added) | 73 | 13.1% |
| Roof (additional insulation) | 68 | 12.2% |
| Windows (replaced) | 116 | 20.8% |
| Any component | 284 | 50.8% |

#### Exterior Walls — median U [W/(m²·K)]

| Era | Unrenovated n | Unrenovated median | Renovated n | Renovated median | Δ |
|---|---|---|---|---|---|
| pre-1960 | 57 | **0.599** | 17 | **0.236** | −0.363 (−61%) |
| 1950–1975 | 219 | **0.210** | 27 | **0.263** | +0.053 |
| 1960–1980 | 106 | **0.295** | 12 | **0.267** | −0.028 |
| mixed | 63 | **0.190** | 7 | **0.225** | +0.035 |

→ Pre-1960 masonry buildings show a **61% U-value reduction** from renovation. Post-1960 concrete buildings show near-zero difference — they were built with insulation; renovations targeted other components.

#### Roof / Attic Floor — median U [W/(m²·K)]

| Era | Unrenovated n | Unrenovated median | Renovated n | Renovated median | Δ |
|---|---|---|---|---|---|
| pre-1960 | 55 | **0.314** | 14 | **0.122** | −0.192 (−61%) |
| 1950–1975 | 223 | **0.138** | 21 | **0.139** | −0.001 |
| 1960–1980 | 100 | **0.138** | 16 | **0.112** | −0.026 |
| mixed | 64 | **0.136** | 6 | **0.133** | −0.003 |

→ Same pattern: massive improvement for pre-1960, negligible for post-1960.

#### Windows — median U [W/(m²·K)]

| Era | Unrenovated n | Unrenovated median | Renovated n | Renovated median | Δ |
|---|---|---|---|---|---|
| pre-1960 | 46 | **2.500** | 28 | **2.000** | −0.500 (−20%) |
| 1950–1975 | 210 | **1.900** | 37 | **1.910** | −0.010 |
| 1960–1980 | 91 | **1.900** | 28 | **1.800** | −0.100 |
| mixed | 63 | **2.000** | 8 | **2.025** | +0.025 |

→ Window renovation effect is modest even for pre-1960 (−20%). BETSI surveyors couldn't reliably detect low-e coatings — renovated windows may perform better than measured.

#### Ground Floor — median U [W/(m²·K)] (proxy: any renovation)

| Era | Unrenovated n | Unrenovated median | Renovated n | Renovated median | Δ |
|---|---|---|---|---|---|
| pre-1960 | 18 | **0.324** | 53 | **0.304** | −0.020 |
| 1950–1975 | 124 | **0.245** | 111 | **0.285** | +0.039 |
| 1960–1980 | 55 | **0.216** | 56 | **0.265** | +0.049 |
| mixed | 42 | **0.214** | 18 | **0.424** | +0.210 |

→ Ground floor shows **no improvement** from renovation (and sometimes worse in "renovated" buildings). This is expected — floor renovations are rare, and the `any_renovated` proxy captures unrelated work (pipes, wet rooms).

#### Key implication for CMF baseline

The TABULA/Boverket population-mean U-values (§13.1–13.3) are **not suitable as "as-built" targets**. For an unrenovated baseline, use the **unrenovated medians** above. The difference is largest for pre-1960 walls (TABULA 0.58 vs unrenovated 0.599 — close) but significant for post-1960 walls (TABULA 0.41 vs unrenovated **0.210** — TABULA is 2× too high because it averages in poorly-insulated pre-1960 buildings reclassified into this era band by population weighting).

### 13.6 Validation Checklist

When computing archetype U-values from BETSI layer data:

1. **Compare per-building U-values** against `FB_Klimat.csv` pre-computed values (columns `FB52 UA-värde ytterväggar`, `FB56 UA-värde vindsbjälklag`, etc.)
2. **Compare era-cluster medians** against the tables above
3. **Watch for thermal bridge corrections** — `FB_Klimat` values `inkl köldbryggor` add ~15–20% to UA; our layer-stack calculations do NOT include thermal bridges
4. **Window U-values** in the per-building data may differ from population means because surveyor field estimates were sometimes inaccurate for low-e glass
5. **Use unrenovated medians (§13.5)** as targets for as-built baselines, not population averages

---

## 14. Component Areas for Archetype Geometry

### 14.1 Exterior Wall Facade Area (10⁶ m²)

| Material | FH Area (10⁶ m²) |
|---|---|
| Tegel (brick) | 43 ± 11 |
| Puts (render) | 41 ± 11 |
| Trä (wood) | 14 ± 5 |
| Plåt (sheet metal) | 5 ± 2 |
| Skivor (boards) | 4 ± 3 |
| Övriga (other) | 4 ± 2 |

→ Brick + render dominate FH facades (~77% of area). Wood is secondary.

### 14.2 Roof Total Area

| Component | Total FH (10⁶ m²) |
|---|---|
| Entire roof construction | 66 |
| Horisontellt vindsbjälklag only | 61.6 ± 10.1 |

**Vindsbjälklag area by age class:**

| Age class | Area (10⁶ m²) |
|---|---|
| –1960 | 22.3 ± 4.5 |
| 1961–75 | 18.7 ± 4.2 |
| 1976–85 | 4.6 ± 0.9 |
| 1986–95 | 12.4 ± 5.2 |
| 1996–05 | 3.6 ± 2.7 |

### 14.3 Ground Floor / Basement Slab Area

**Platta på mark / källargolv — Total: 61.8 ± 10.6 (10⁶ m²):**

| Age class | Area (10⁶ m²) |
|---|---|
| –1960 | 24.8 ± 5.7 |
| 1961–75 | 17.8 ± 4.3 |
| 1976–85 | 4.8 ± 0.9 |
| 1986–95 | 12.1 ± 4.9 |
| 1996–05 | 2.3 ± 0.7 |

**Crawl space floor — Total: 6.5 ± 3.9 (10⁶ m²)** — all age-class breakdowns statistically uncertain for FH.

### 14.4 Window Area

**Total: 29.4 ± 4.9 (10⁶ m²)**

| Age class | Area (10⁶ m²) |
|---|---|
| –1960 | 11.9 ± 2.0 |
| 1961–75 | 9.2 ± 2.2 |
| 1976–85 | 1.7 ± 0.4 |
| 1986–95 | 4.5 ± 1.9 |
| 1996–05 | 2.1 ± 1.2 |

**Orientation distribution (approximately uniform):**

| Direction | Share (%) | Area (10⁶ m²) |
|---|---|---|
| North | 21 | 6.2 |
| South | 25 | 7.5 |
| West | 28 | 8.4 |
| East | 26 | 7.7 |

### 14.5 Window-to-Wall Ratio (derived)

Total window area ~29.4M m² ÷ total facade area ~111M m² ≈ **0.26** (26% glazing ratio). Useful as default when per-building data is incomplete.

---

## 15. Building Typology & Structural Systems

### 15.1 Building Type Distribution

| Type (Swedish) | English | Share (%) |
|---|---|---|
| Lamellhus | Slab block | 41 ± 10 |
| Flerbostadsvilla | Multi-family villa | 25 ± 12 |
| Punkthus | Point block | 8 ± 3 |
| Skivhus | Tower slab | 8 ± 3 |
| Loftgångshus | Gallery access | 7 ± 4 |
| Radhus | Terraced house | 3 ± 3 |
| Annat | Other | 8 ± 4 |

**For 1961–75 (miljonprogram):** Lamellhus+Skivhus = 79%, Loftgångshus = 13%, Punkthus = 6%.

### 15.2 Number of Stories

| Stories above ground | Share (%) |
|---|---|
| 1 | 5 ± 3 |
| 2 | 20 ± 4 |
| 3 | 22 ± 4 |
| **4** | **30 ± 4** |
| 5 | 7 ± 1 |
| 6 | 6 ± 2 |
| 7 | 5 ± 1 |
| 8 | 2 ± 1 |
| 9+ | ~4 |

Most common: **4 stories** (30%), then 3 (22%), 2 (20%). This aligns with 1960 elevator regulation: hiss required for ≥4 stories → many 3-story buildings were built to avoid the cost.

### 15.3 Foundation Type Distribution

| Type | Share (%) |
|---|---|
| Enbart källare (basement only) | **52 ± 9** |
| Platta på mark (slab on ground) | **27 ± 6** |
| Krypgrund (crawl space) | 9 ± 8 |
| Källare + platta på mark | 8 ± 5 |
| Krypgrund + källare | 4 ± 3 |
| All three combined | <1 |

**Crawl space types (all building types combined):**

| Type | Share of crawl spaces (%) |
|---|---|
| Uteluftsventilerad (outside-air ventilated) | 60 ± 13 |
| Torpargrund (traditional) | 25 ± 12 |
| Oventilerad (unventilated) | 7 ± 6 |
| Plintgrund (pier) | 6 ± 5 |
| Inneluftventilerad (inside-air ventilated) | 1 ± 1 |

### 15.4 Roof Form Distribution

| Form | FH Share (%) |
|---|---|
| Sadeltak (gable) | 73.8 ± 7.3 |
| Valmat (hipped) | 10.4 ± 5.5 |
| Motfallstak (counter-pitch) | 6.1 ± 3.3 |
| Mansardtak (mansard) | 4.3 ± 3.9 |
| Pulpettak (mono-pitch) | 3.5 ± 1.8 |
| Horisontaltak (flat) | 1.5 ± 0.8 |

### 15.5 Roof Material Distribution (FH)

| Material | Area (10⁶ m²) |
|---|---|
| Betong (concrete tiles) | 30 ± 10 |
| Stålplåt (steel sheet) | 24 ± 11 |
| Tegel (clay tiles) | 14 ± 6 |
| Takpapp (roofing felt) | 13 ± 4 |
| Annan plåt (other metal) | 3 ± 2 |
| Övriga (other) | 2 ± 1 |

### 15.6 Tenure Form

| Age class | Bostadsrätt (%) | Hyresrätt (%) |
|---|---|---|
| –1960 | 27 ± 10 | 73 ± 10 |
| 1961–75 | 28 ± 12 | 72 ± 12 |
| 1976–85 | 33 ± 14 | 67 ± 14 |
| 1986–95 | 35 ± 22 | 65 ± 22 |
| 1996–05 | 72 ± 29 | 28 ± 29 |
| **Total** | **33 ± 10** | **67 ± 10** |

→ Hyresrätt dominates overall but bostadsrätt surged post-1990.

---

## 16. HVAC Systems by Era

### 16.1 Ventilation System (by share of heated floor area served)

| Age class | Självdrag (natural) | F-system (exhaust) | FT (supply+exhaust) | FTX (with heat recovery) | FVP (exhaust air HP) |
|---|---|---|---|---|---|
| –1960 | **Dominant** | Minor | Rare | Rare | Rare |
| 1961–75 | Small | **Dominant** | Minor | Minor | Minor |
| 1976–85 | Small | **Dominant** | Minor | Minor | Minor |
| 1986–95 | Very small | Minor | — | **Dominant** | Some |
| 1996–05 | Very small | Moderate | — | Mix | Mix |

- Natural draft (självdrag) only significant in pre-1960 buildings.
- F-system (exhaust only) dominates 1961–1985.
- 1989 BBR regulation introduced heat recovery requirement → FTX and FVP surge in 1986–95.
- 1994 BBR dropped heat recovery requirement for buildings heated with renewable energy → mixed in 1996–05.

**OVK (Obligatorisk ventilationskontroll) compliance:**

| Age class | Approved (%) | Not approved (%) | Partially (%) |
|---|---|---|---|
| –1960 | 52 ± 17 | 38 ± 16 | 10 ± 16 |
| 1961–75 | 82 ± 10 | 17 ± 10 | 0 |
| 1976–85 | 67 ± 20 | 33 ± 20 | 1 |
| 1986–95 | 56 ± 21 | 42 ± 21 | 2 |
| 1996–05 | 72 ± 15 | 27 ± 15 | 0 |
| **Total** | **61 ± 10** | **34 ± 10** | **5 ± 8** |

### 16.2 Heating Source

| Source | Share of buildings (%) | Share of Atemp (%) |
|---|---|---|
| Fjärrvärme (district heating) | **64** | **81** |
| Värmepump (excl. exhaust air) | 15 | 6 |
| Elvärme (electric) | 11 | 5 |
| Olja/Gas (oil/gas) | 7 | 6 |
| Biobränsle (biomass) | 2 | 1 |
| Frånluftsvärmepump (exhaust air HP) | — | 2 |

→ **81% of heated area** uses district heating. Small buildings in smaller cities more often use electric or heat pumps.

**Heat pump types in FH:**

| Type | Share (%) |
|---|---|
| Bergvärme (ground source) | 44 ± 23 |
| Frånluft (exhaust air) | 39 ± 24 |
| Uteluft (air source) | 16 ± 28 |

---

## 17. Indoor Climate Reference Values

Use these for simulation boundary conditions and validation.

### 17.1 Indoor Temperature

| Building type | Mean T (°C) |
|---|---|
| Småhus | 21.2 ± 0.2 |
| **Flerbostadshus** | **22.3 ± 0.2** |

Distribution in FH: 23°C is the most common (30%), followed by 22°C (23%). Temperature is generally **lower in older buildings**.

→ **Use 22°C as heating setpoint** for FH simulations (matches BBR reference but actual average is slightly higher).

### 17.2 Air Change Rate

| Building type | Mean ACH (h⁻¹) |
|---|---|
| Småhus | 0.40 |
| **Flerbostadshus** | **0.52** |

Distribution in FH:

| ACH range | Share (%) |
|---|---|
| <0.2 | 10.0 |
| 0.2–0.3 | 11.5 |
| 0.3–0.4 | 15.7 |
| 0.4–0.5 | 16.3 |
| 0.5–0.6 | 14.5 |
| 0.6–0.7 | 10.7 |
| 0.7–0.8 | 7.3 |
| 0.8–0.9 | 6.1 |
| >0.9 | 7.8 |

→ BBR minimum is 0.35 l/s/m² ≈ 0.52 ACH (at 2.4m ceiling). Mean FH value meets this exactly.

### 17.3 Relative Humidity

| Building type | Mean RH (%) |
|---|---|
| Småhus | ~33 |
| **Flerbostadshus** | **~30** |

FH distribution: 30–35% RH is most common (41%), then 25–30% (32%).

### 17.4 Moisture Supplement

| Building type | Moisture supplement (g/m³) |
|---|---|
| Småhus | 1.8 ± 0.1 |
| **Flerbostadshus** | **1.2 ± 0.2** |

---

## 18. Renovation & Damage Data

### 18.1 Damage Prevalence by Component

**Percent of FH buildings with damage/defects needing repair:**

| Component | FH % with damage |
|---|---|
| Grund (foundation) | 8 ± 4 |
| Installationer (HVAC/plumbing/electric) | 17 ± 8 |
| Fönster (windows/doors) | 17 ± 11 |
| Våtrum (wet rooms) | 12 ± 7 |
| Ytterväggar (exterior walls) | **20 ± 9** |
| Yttertak (roof) | 17 ± 5 |
| Invändiga ytskikt (interior finishes) | 8 ± 7 |

→ Overall, **~45% of FH** have some type of damage (vs. 69% of småhus). Most are not severe.

### 18.2 Moisture/Mould Damage

- 13 ± 5% of FH have moisture damage that may affect indoor environment (vs. 38% småhus).
- Total cost to remediate all moisture damage in FH: **6.2 ± 3.3 billion SEK**.

### 18.3 Total Repair Costs

| Scope | Cost (billion SEK) |
|---|---|
| All FH damage (immediate if done now) | **65 ± 27** |
| All building types combined | 267 ± 40 |
| Short-term urgent repairs (all types) | ~224 |
| Long-term deferred maintenance (all types) | ~30 |
| Moisture damage only (all types) | ~101 |
| Noise remediation (all types) | 25–50 |

Short-term cost breakdown (all building types):

| Component | Cost (million SEK) |
|---|---|
| Foundation | 64,352 ± 14,464 |
| Installations | 14,464 ± 13,669 |
| Windows | 25,958 ± 7,979 |
| Wet rooms | 20,097 ± 5,967 |
| Exterior walls | 42,928 ± 12,750 |
| Roof | 44,430 ± 9,626 |
| Interior finishes | 11,529 ± 5,038 |

Reference: Annual maintenance cost for FH/lokaler ≈ 150 SEK/m²/year (SCB 2007).

### 18.4 Renovation History (share of FH where component was renovated since construction)

| Component | FH % renovated |
|---|---|
| Avloppsstammar (drain pipes) | 23 ± 8 |
| Elsystem (electrical) | 20 ± 9 |
| Dränering (drainage) | 9 ± 4 |
| Ventilation | 15 ± 5 |
| Våtrum (wet rooms) | 35 ± 8 |

**And within last 3 years only:**

| Component | FH % renovated in last 3 yrs | Cost (million SEK) |
|---|---|---|
| Grund | 4 ± 3 | 518 ± 470 |
| Installationer | 18 ± 7 | 15,004 ± 5,745 |
| Fönster/dörrar | 8 ± 4 | 6,019 ± 3,143 |
| Våtrum | 12 ± 7 | 5,140 ± 2,378 |
| Ytterväggar | 11 ± 7 | 5,919 ± 2,937 |
| Yttertak | 4 ± 2 | 3,794 ± 3,264 |
| Invändiga ytskikt | 11 ± 6 | 5,759 ± 4,691 |

### 18.5 Miljonprogram Renovation Status (1961–75 FH)

From BETSI vs. BOOM-group (KTH) 2002 estimates:

| Component | BETSI (apartments renovated) | BOOM-2002 estimate |
|---|---|---|
| Dränering | 25,000 | No data |
| El | 50,000 | 50,000 |
| Avlopp (drain pipes) | 108,000 | 80,000 |
| Våtrum | 200,000 | 110,000 |
| Ventilation | 190,000 | 75,000 |

Key context:
- ~78% of miljonprogram buildings had NOT been modernized by 2008 (Industrifakta).
- SABO estimated 300,000 apartments still need renovation.
- At then-current pace, full renovation would take ~30 years.

**1961–75 FH component renovation rates:**

| Component | FH % renovated |
|---|---|
| Avloppsstammar | 13 ± 7 |
| Elsystem | 6 ± 5 |
| Dränering | 3 ± 3 |
| Ventilation | 21 ± 8 |
| Våtrum | 36 ± 16 |

### 18.6 Additional Insulation Feasibility (cultural heritage constraint)

| Component | Can insulate (%) | Cannot (%) | Uncertain (%) |
|---|---|---|---|
| Ytterväggar (facades) | 41 | 31 | 28 |
| Vindsbjälklag (attic floor) | 68 | 15 | 17 |

→ **Only 41% of FH facades** can be additionally insulated without cultural-historical concerns. This is a major constraint for renovation scenarios.

---

## 19. Hazardous Materials by Era

Important for renovation cost estimation and feasibility.

### 19.1 Asbestos

| Age class | FH with asbestos (%) |
|---|---|
| –1960 | **69 ± 12** |
| 1961–75 | **75 ± 14** |
| 1976–85 | 12 ± 12 |

→ ~50% of all FH contain asbestos (mainly pre-1975). Banned in 1976.
Found in: ventilation ducts, tile adhesive/grout, floor tiles, fire insulation, eternit facades/roofs.

### 19.2 Blue Aerated Concrete (Blå lättbetong) — Radon source

Used 1929–1975. Emits radon.

| Age class | Confirmed (%) | Probable (%) | Unknown (%) |
|---|---|---|---|
| –1960 | 14.3 ± 15.2 | 7.8 ± 5.4 | 26.7 ± 10.6 |
| 1961–75 | 8.5 ± 4.4 | 30.9 ± 13.1 | 27.1 ± 9.3 |
| 1976–85 | 0.1 ± 0.1 | 0.2 ± 0.4 | 4.7 ± 5.5 |

→ Up to **~47% of 1961–75 FH** may contain blue aerated concrete (confirmed + probable).

### 19.3 PCB

Used 1956–1973. Found in sealants, plasticizers, insulating glass. At least **17,500 buildings** in Sweden likely contain PCB. Only 34% of the legally required 52,000 buildings had been inventoried by 2007–2008.

### 19.4 CFCs (Freoner)

Banned (CFC in 1999, HCFC refill in 2001). ~8% of FH contain CFCs (varies by age; highest in 1976–85 at ~15%).

### 19.5 Radon Levels

~75,000 apartments exceed 200 Bq/m³ threshold (the 2020 goal level).

---

## 20. Error Sources & Data Quality

From the report's own error analysis (Chapter 10):

1. **Missing/poor documentation** — ~40% of buildings had missing or low-quality drawings and technical descriptions.
2. **Surveyor variation** — Different surveyors made very different estimates for similar buildings. Only a 2-day training was provided.
3. **No destructive testing** — All inspections were visual only. Hidden damage is underestimated.
4. **Dual-purpose buildings** — ~20,000 radhus apartments are classified as FH rather than småhus in tax records. ~4,000 buildings affected.
5. **Control inspections** — Boverket re-inspected 13 FH with more experienced inspectors. Differences were "large and varied" — more damage was found in control inspections.
6. **Damage cost underestimation** — Costs are calculated assuming individual repairs, no bundling savings. Owner-refused buildings may be underrepresented.
7. **Construction layers** — When drawings were missing, surveyors estimated construction layers based on experience. This affects both material codes and thicknesses in FB52/56/33 data.

### Implications for our archetype work

- **Layer data quality varies**: Buildings with good drawings yield accurate constructions. Buildings where surveyors estimated may have simplified/wrong layer stacks.
- **Validate individual building U-values** against `FB_Klimat.csv` pre-computed values. Flag buildings where computed and pre-computed U-values differ by >20%.
- **The population statistics (Section 13) are more reliable** than any individual building record because sampling errors average out.
- **Window U-values are least reliable** — surveyors couldn't reliably detect low-e coatings during visual inspection.

---

## 21. Mapping BETSI Age Classes to EPSM Eras

BETSI uses five age classes for population statistics. Our EPSM archetype eras (derived from structural system) map approximately as follows:

| BETSI Age Class | EPSM EstimatedEra | Structural System | Typical Construction |
|---|---|---|---|
| –1960 | pre-1960 | Masonry (murverk) | Load-bearing brick/stone walls, natural draft ventilation, 1.0+ m thick masonry, no/minimal insulation |
| 1961–75 | 1950–1975 | Concrete walls (väggar av betong) | Prefab or cast concrete, F-system ventilation, 50–100mm mineral wool, miljonprogram era |
| 1976–85 | 1960–1980 | All-concrete (alla väggar av betong) | Improved insulation (100–150mm), concrete sandwich panels, F-system |
| 1986–95 | (mixed / post-1985) | Timber frame / mixed | FTX ventilation (heat recovery mandate), 150–200mm insulation, modern materials |
| 1996–05 | (mixed / post-1990) | Timber frame / newer | Mixed ventilation, 200mm+ insulation, energy-conscious design |

**Caveat**: The BETSI report age classes use actual construction year (known from tax records), while our EPSM `EstimatedEra` uses structural system as a proxy. There is overlap between these — a concrete wall building in the pre-1960 class might have been built in the 1950s, or in the 1880s with later concrete reinforcement. Always cross-check against FC3 renovation years when available.

---

## 22. Hot Water System Data

Relevant for full-building energy simulation.

### 22.1 VVC (Domestic Hot Water Circulation)

- ~80% of FH have VVC (circulation) systems.
- BBR requires ≥50°C at tap point.

**Temperature after water heater:**

| Range | FH share (%) |
|---|---|
| <45°C | 1 ± 1 |
| 45–49°C | 9 ± 8 |
| 50–60°C | 72 ± 9 |
| >60°C | 18 ± 7 |

**Temperature at tap point (all FH):**

| Range | Share (%) |
|---|---|
| <45°C | 7 ± 5 |
| 45–49°C | 18 ± 7 |
| 50–60°C | 69 ± 7 |
| >60°C | 5 ± 3 |

→ **~25% of FH** do not meet the 50°C minimum at tap point.

**VVC temperature difference (outlet vs return):**
- Only **30 ± 11%** meet the ≤5°C recommendation (SS-EN 806-2).
- 1986–95 era worst: only 16% meet the standard.

### 22.2 Legionella

- 20% of tested FH samples were positive (14/71 samples).
- No Swedish limits exist; EU guidance recommends action >100 CFU/100ml, sanitation >1000 CFU/100ml.

---

## 23. Accessibility & Elevator Data

### 23.1 Elevator Presence

- **26 ± 7%** of all FH have an elevator; **37 ± 9%** of lokaler.
- For buildings with ≥3 stories: **45 ± 11% LACK an elevator**.
- Hiss regulation: required for ≥4 stories since 1960, for ≥3 stories since 1977.

**FH with ≥3 stories lacking elevator by age:**

| Age class | Without hiss (%) |
|---|---|
| –1960 | 66 ± 20 |
| 1961–75 | 52 ± 15 |
| 1976–85 | 14 ± 12 |
| 1986–95 | 3 ± 5 |
| 1996–05 | 3 ± 6 |

### 23.2 Entry Accessibility (no steps)

| Age class | Accessible entry (%) |
|---|---|
| –1960 | 27 ± 16 |
| 1961–75 | 62 ± 11 |
| 1976–85 | 68 ± 14 |
| 1986–95 | 75 ± 21 |
| 1996–05 | 90 ± 11 |

→ **78 ± 6%** of all FH have apartments that cannot be reached without using stairs.

---

## 24. CMF Baseline Gap Analysis (vs BETSI Unrenovated Targets)

The CMF baseline represents **as-built, unrenovated** constructions. Targets are the **unrenovated median U-values** from §13.5, derived from BETSI buildings with no component-specific renovation recorded in FC3.

Source: `debug_baseline_vs_betsi.py`

### 24.1 BETSI Unrenovated Targets by Era

| EPSM Era | BETSI Era | Wall | Roof | Floor | Window |
|---|---|---|---|---|---|
| CMF_1940/1950 | pre-1960 | 0.599 | 0.314 | 0.324 | 2.500 |
| CMF_1960 | 1950–1975 | 0.210 | 0.138 | 0.245 | 1.900 |
| CMF_1970/1980 | 1960–1980 | 0.295 | 0.138 | 0.216 | 1.900 |

### 24.2 Full Gap Analysis — All Archetypes

| Archetype | Component | Current U | Target U | Ratio | Status |
|---|---|---|---|---|---|
| CMF_1940_1 | EXT_WALL | 1.506 | 0.599 | 2.51× | ❌ +151% — missing insulation layers |
| CMF_1940_1 | TOP_FLOOR | 0.301 | 0.314 | 0.96× | ✅ OK |
| CMF_1940_1 | GROUND_FLOOR | 0.989 | 0.324 | 3.05× | ❌ +205% — missing insulation |
| CMF_1940_1 | WINDOW | 2.220 | 2.500 | 0.89× | ⚠ Close (−11%) |
| CMF_1950 | EXT_WALL | — | 0.599 | — | ⚠ No EXT_WALL element in output |
| CMF_1950 | TOP_FLOOR | 1.867 | 0.314 | 5.95× | ❌ +495% — layer stack broken |
| CMF_1950 | GROUND_FLOOR | 0.916 | 0.324 | 2.83× | ❌ +183% — missing insulation |
| CMF_1950 | WINDOW | 2.220 | 2.500 | 0.89× | ⚠ Close (−11%) |
| **CMF_1960_1** | **EXT_WALL** | **0.411** | **0.210** | **1.96×** | **❌ +96% — too little MW** |
| **CMF_1960_1** | **TOP_FLOOR** | **0.201** | **0.138** | **1.46×** | **❌ +46% — needs ~115mm more loose fill** |
| **CMF_1960_1** | **GROUND_FLOOR** | **0.235** | **0.245** | **0.96×** | **✅ OK** |
| **CMF_1960_1** | **WINDOW** | **2.220** | **1.900** | **1.17×** | **⚠ Close (+17%)** |
| CMF_1960_2 | EXT_WALL | 0.599 | 0.210 | 2.85× | ❌ +185% |
| CMF_1960_2 | TOP_FLOOR | 4.179 | 0.138 | 30.28× | ❌ Layer stack broken |
| CMF_1960_2 | GROUND_FLOOR | 0.919 | 0.245 | 3.75× | ❌ +275% |
| CMF_1960_2 | WINDOW | 2.220 | 1.900 | 1.17× | ⚠ Close (+17%) |
| CMF_1970 | EXT_WALL | 1.225 | 0.295 | 4.15× | ❌ +315% — missing insulation |
| CMF_1970 | TOP_FLOOR | 0.139 | 0.138 | 1.01× | ✅ OK |
| CMF_1970 | GROUND_FLOOR | 0.513 | 0.216 | 2.38× | ❌ +138% |
| CMF_1970 | WINDOW | 2.220 | 1.900 | 1.17× | ⚠ Close (+17%) |
| CMF_1980 | EXT_WALL | 1.225 | 0.295 | 4.15× | ❌ +315% — missing insulation |
| CMF_1980 | TOP_FLOOR | 0.139 | 0.138 | 1.01× | ✅ OK |
| CMF_1980 | GROUND_FLOOR | 0.513 | 0.216 | 2.38× | ❌ +138% |
| CMF_1980 | WINDOW | 2.040 | 1.900 | 1.07× | ✅ OK |

### 24.3 Summary

**Passing (within ±10%):** 6 / 24 component-archetype pairs.
**Close (10–20%):** 5 / 24 (mostly windows — TABULA overshoots by ~17%).
**Failing (>20% off):** 13 / 24 — dominated by walls and floors missing insulation layers.

The previous validation (against TABULA population averages) showed CMF_1960_1 walls and roof as passing. Against **unrenovated targets**, both fail — the TABULA population mean for 1961–75 walls (0.41) is 2× the unrenovated median (0.21) because population weighting blends in poorly-insulated pre-1960 masonry buildings.

### 24.4 Remaining work

1. **Fix `cellular_plastic` EP material** — remap from Roof Membrane (k=0.16) to proper XPS/EPS (k≈0.035). See §5 audit.
2. **CMF_1960_1 EXT_WALL** — current 95mm MW gives U=0.41. Needs ~200mm MW total to reach U≈0.21.
3. **CMF_1960_1 TOP_FLOOR** — current 230mm MW gives U=0.20. Needs ~340mm total to reach U≈0.14.
4. **CMF_1970/1980 EXT_WALL** — layer stack has no insulation (U=1.225). Needs ~120mm MW to reach U≈0.30.
5. **Ground floors (all archetypes except 1960_1)** — all missing slab insulation. Blocked by cellular_plastic fix.
6. **CMF_1950 TOP_FLOOR** — U=1.87 suggests layer stack is broken (possibly reversed or missing insulation).
7. **CMF_1960_2** — all components far off; needs full reconstruction.
8. **Window U-values** — update from TABULA (2.22) to BETSI unrenovated (1.90) for CMF_1960/1970 eras.
9. **Update TABULA reference values in `standards.py`** — replace population-mean targets with unrenovated medians for validation.
