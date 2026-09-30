# CMF 1940s, 1950s and 1960s: MFH LoD2 preparation

Status: source transcription and completed MF SE.01 Existing fit. The 1940s
construction is canonical and the 1950s construction is a named alternative.
Both pass the catalogue's nominal LoD2 acceptance checks against the retained
TABULA-era LoD1 targets. The alternative adds no separate matrix slots.

## Source and reproducibility

User-supplied workbook: `Material_Database_Merged.xlsx` in `~/Downloads`.
SHA-256: `8ca60c774a1e503e9a3de556f7f7933190e6960853093aca21e491d40b45c552`.
The row-preserving transcription is
[`mfh_cmf_decades_workbook.json`](../src/epsm_data/datasets/layered/evidence/mfh_cmf_decades_workbook.json).
Recreate it with:

```sh
python tools/prepare_mfh_cmf_workbook.py \
  ~/Downloads/Material_Database_Merged.xlsx \
  src/epsm_data/datasets/layered/evidence/mfh_cmf_decades_workbook.json
```

The extractor needs `openpyxl`; it is an optional evidence tool, not a runtime
dependency. The snapshot retains the source rows from `Layers!A:P` and
`Components!A:F`, plus the material-register rows needed for review. It does
not calculate U-values or repair the workbook. Workbook notes refer to BUD_MI
and *Så byggdes husen 1880–2010*, but the book edition, page, drawing and
construction date behind each CMF variant still need verification.

## Mapping into EPSM

EPSM LoD1 uses SE.01 through 1960 and SE.02 for 1961–1975. Each
category/era/state construction covers three zones and four ventilation classes.
The source variants must remain distinct even where they share a catalogue
target.

| Workbook variant | Source layers | Intended use | Catalogue position |
| --- | ---: | --- | --- |
| `CMF_1940_1` | 35 | 1940s canonical representative | MF SE.01 Existing, 12 slots |
| `CMF_1950` | 24 | 1950s named alternative | MF SE.01 Existing, same targets, zero additional slots |
| `CMF_1960.1` | 24 | Compare with the active calibrated representative | MF SE.02 Existing, provisionally |
| `CMF_1960_2` | 21 | Separate 1960s alternative | MF SE.02 Existing, provisionally |

The CMF year in an identifier is not a verified construction year. The active
MF SE.02 representative assumes 1965 for `CMF_1960_1`; this does not establish
that either workbook 1960s variant was built after 1960. If the source year is
1960 exactly, EPSM's current year boundary places it in SE.01. Only the 1940s
variant is assigned to the 12 SE.01 Existing catalogue slots.

Current **Existing** LoD1 comparison targets, W/(m²·K), except infiltration in
1/h. These are effective catalogue targets, not workbook measurements:

| Role | MF SE.01 | MF SE.02 | Comparison boundary |
| --- | ---: | ---: | --- |
| External wall | 0.580 | 0.410 | Heated space to outdoors |
| Top thermal boundary | 0.360 | 0.200 | Heated space to attic; use `TOPFLOOR`, not cold roof covering |
| Intermediate floor | 2.151 | 1.710 | Internal floor |
| Internal partition | 0.823 | 0.582 | Internal partition |
| Whole window Uw | 2.220 | 2.220 | Whole window; workbook glazing rows are ignored |
| Ground floor | 0.325 | 0.258 | Effective slab-on-ground, not one-dimensional layer U |
| Basement wall | 0.702 | 0.702 | Effective below-ground wall, not one-dimensional layer U |
| Infiltration | 0.400 | 0.400 | Effective background air changes; no layer fit |

The exact targets and provenance are in the live parametric catalogue. The
five-role catalogue LoD2 nominal alignment rule is within ±2% for roof/top,
external wall, intermediate floor, internal wall and whole window. Ground and
basement physics require separate boundary validation; matching their effective
LoD1 values by changing solid layers would conflate different quantities.

## Source coverage and repairs to investigate

| Variant | Useful source assemblies | Missing or unresolved before acceptance |
| --- | --- | --- |
| 1940 | Top floor, external wall, intermediate floors and partitions | No ground/basement assembly. Window and small-window rows 98–102 are ignored. Composite wall row 96 has no area fractions. Wood shavings, coke ash and vinyl flooring lack both material links; ceramic tile lacks a Honeybee link; two material names have no register match. |
| 1950 | Cold roof, top floor, three height-dependent wall variants and bottom floor | No intermediate floor or partition. Bottom-floor boundary must be established. Window row 21 is ignored. Composite rows 13, 17, 19 and 21 lack area fractions. Slag, plastic mat and coke ash lack links; `concrete_micxed_with_sawdust` differs from the material register spelling. |
| 1960.1 | Cold roof, top floor, brick and balcony walls and bottom floor | No workbook intermediate floor or partition. Window rows 43–46 are ignored. Composite wall rows 32, 33 and 36 lack fractions; several material names/links need reconciliation. `asphalt_board` has duplicate material rows. Active MF SE.02 layers already contain additional documented representative choices. |
| 1960.2 | Cold roof, top floor, two wall variants and bearing partition | No bottom floor, intermediate floor or nonbearing partition. Window rows 67–69 are ignored. Composite rows 60 and 64 lack fractions; asbestos cement, asphalt board and foil lack links. |

`Window_Materials!A:F` lists generic frame and glass mappings, but supplies no
complete whole-window Uw, SHGC or visible transmittance for these variants.
The shared LoD1 Uw 2.22 is retained as the TABULA-era target; it does not
validate the ignored window layers. Boverket's typical original coupled
1940s/1950s windows are about 2.8–3.0 W/(m²K), so the fitted window may
represent replacement or a mixed stock. The simple whole-window SHGC 0.70 and
VT 0.75 remain explicit optical assumptions. [Boverket period examples](https://www.boverket.se/sv/energiguiden/energieffektivisera-flerbostadshus/energirenovera/byggide/klarlagg-forutsattningarna/atgarder-i-typiska-byggnader/).

The workbook's `Progress Notes` marks several components with `X`; those marks
are inventory notes, not a passed EPSM construction or LoD2 check. Preserve
the workbook's thicknesses, ignored flags and notes in the source record, then
record every representative substitution and added assembly separately.

## Completed 1940s and 1950s fitting

The active authoring script is `tools/author_historic_mf.py`. It preserves
workbook row locators and original source depths for selected rows. The
additional wood-fibre insulation/lining is labelled as a representative
TABULA fit, not an observed period layer. The 1940s attic retains its 150 mm
shavings depth while its assumed conductivity changes from 0.062 to 0.078
W/(mK). For the 1940s intermediate floor, the representative selects the
source 160 mm structural slab and 50 mm screed, with an assumed 8 mm underlay;
the alternative living-room ash/floorboard and bathroom rows remain in the
frozen evidence snapshot. The 1950s missing intermediate floor and partition
borrow the fitted 1940s family explicitly.

| Role | Retained SE.01 target | 1940s nominal | 1950s nominal | Main fit |
| --- | ---: | ---: | ---: | --- |
| External wall | 0.580 | 0.579 | 0.581 | Added wood-fibre insulation, 74/86 mm |
| Top floor | 0.360 | 0.360 | 0.359 | Revised shavings λ / added 125 mm wood fibre |
| Intermediate floor | 2.151 | 2.149 | 2.149 | Selected 1940s concrete floor plus 8 mm underlay; borrowed in 1950s |
| Internal partition | 0.823 | 0.820 | 0.820 | Added 63 mm wood-fibre lining; borrowed in 1950s |
| Whole window Uw | 2.220 | 2.220 | 2.220 | Simple TABULA-calibrated window proxy |

Ground-floor and basement-wall layers are representative boundary placeholders.
Their one-dimensional nominal U-values do not match, or validate, the retained
effective ground-contact LoD1 targets. Carbon assessment and full simulation
readiness remain false. The 1940s canonical recipe adds 12 accepted slots;
the 1950s alternative passes the same checks but contributes zero additional
slots. This was the initial 60/1080 acceptance stage. The subsequent
[remaining MF completion](mfh_lod2_remaining.md) brings current acceptance to
228/1080 slots, with 240 recipe slots.

## Original fitting plan and remaining work

1. **Choose the period representatives.** Compare 1940 and 1950 wall/top-floor
   types and choose a canonical SE.01 construction or explicitly extend the
   catalogue to represent decade variants. Compare 1960.1 and 1960.2 with the
   already accepted SE.02 recipe without overwriting it.
2. **Reconstruct complete roles.** Order source layers from outside to inside;
   keep cold roof covering separate from the top thermal boundary. Add any
   missing internal floor, partition, ground/basement and whole-window recipes
   as labelled assumptions with source/locator and caveats. Do not infer a
   ground-contact effective U from the workbook's bottom-floor layers.
3. **Resolve materials and composites.** Correct register/name mismatches by
   documented mapping, obtain or justify Honeybee and Boverket product links,
   and assign composite area fractions from evidence or an explicit
   representative assumption. Review thermophysical and optical properties.
4. **Run an unadjusted nominal calculation.** Record source-depth U and its
   boundary convention for each role before fitting. Compare the five roles
   above to the live era/state snapshot. Adjust only defensible representative
   choices, and log original depth, selected depth, source and rationale.
   Do not silently force all workbook assemblies to match one era mean.
5. **Integrate and accept.** The detailed validator and completeness builder
   now support Existing-only MF decade variants. Verify every material,
   layer, assembly, state and source link; captured target drift; nominal
   Honeybee/core exports; and all 12 classification slots per accepted state.
   Update count-based tests to reflect the actual added records and run the
   full repository suite. Keep ground, carbon and simulation readiness separate.

## Expected catalogue effect

The 1940s canonical recipe adds **12** accepted LoD2 slots. Standard
and Advanced would require independent renovation recipes and evidence; the
workbook does not provide them. The 1960s alternatives can improve or challenge
MF SE.02 but do not add slots to an already accepted state. The active JSON
registries under `src/epsm_data/datasets/layered/` are the authoring database;
the workbook snapshot is review evidence only.
