# Poirazis office reference: building-element evidence

Recorded 2026-09-17 from the user's pasted transcription. The source PDF's
Tables 5.1–5.4, Figures 5.10–5.11 and Appendix E were then checked visually.

Source: Harris Poirazis (2008), *Single and Double Skin Glazed Office Buildings –
Analyses of Energy Use and Indoor Climate*, doctoral thesis (monograph),
Lund University, Report EBD-T--08/8,
ISBN 978-91-85147-23-6. Existing catalogue source ID: `poirazis_2008`.
[Lund University publication record](https://portal.research.lu.se/en/publications/single-and-double-skin-glazed-office-buildings-analyses-of-energy/)
and [full thesis PDF](https://www.lth.se/fileadmin/energi_byggnadsdesign/images/Publikationer/Bok_Dokt_avhandling_HP_G5.pdf).
The university record was checked on 2026-09-17 and confirms the thesis type,
author, year, report number and ISBN.

The user identifies **PUB-013** as the related journal article on ScienceDirect,
DOI [10.1016/j.enbuild.2007.10.011](https://doi.org/10.1016/j.enbuild.2007.10.011).
Keep that article as a separate bibliographic item: the Table 5.1, Table 5.2 and
Figure 5.10 page references below belong to the doctoral thesis. The DOI page
could not be retrieved during this update; the PUB-013 association is user-supplied.

This is the designed office reference already assigned to **Office / SE.05 /
Existing** in the LoD1 catalogue. It is distinct from MF SE.02. These details
are now stored as office source evidence alongside calibrated layers in the shared JSON registries. Table 5.2
**applied U-values govern the thermal reference**, as selected by the user.
Table 5.1 layers remain source evidence and layer-only calculation inputs;
the representative office set now passes catalogue LoD2 with bounded thickness adjustments.

## Table 5.1 — PDF page 137 / printed page 135

The source labels materials **inside to outside** and excludes thermal bridges.
Preserve the listed order pending review of the actual assembly geometry.
Thickness is in m, conductivity in W/(m K), density in kg/m³ and specific heat
in J/(kg K).

| Element | Material | Thickness | Conductivity | Density | Specific heat |
|---|---|---:|---:|---:|---:|
| External wall, long façade | Gypsum board | 0.013 | 0.18 | 758 | 840 |
| External wall, long façade | Mineral wool | 0.1068 | 0.036 | 16 | 754 |
| External wall, long façade | Wood (studs) | 0.011 | 0.14 | 500 | 2300 |
| External wall, long façade | Gypsum board | 0.009 | 0.18 | 758 | 840 |
| External wall, long façade | Air gap | 0.04 | 0.25 | 1.2 | 1006 |
| External wall, long façade | Facing bricks | 0.12 | 0.58 | 1500 | 840 |
| External wall, short façade | Concrete | 0.2 | 1.7 | 2300 | 880 |
| External wall, short façade | Mineral wool | 0.145 | 0.036 | 16 | 754 |
| External wall, short façade | Air gap | 0.04 | 0.25 | 1.2 | 1006 |
| External wall, short façade | Facing bricks | 0.12 | 0.58 | 1500 | 840 |
| Internal wall | Gypsum | 0.026 | 0.22 | 970 | 1090 |
| Internal wall | Air gap | 0.032 | 0.17 | 1.2 | 1006 |
| Internal wall | Light insulation | 0.03 | 0.036 | 20 | 750 |
| Internal wall | Air gap | 0.032 | 0.17 | 1.2 | 1006 |
| Internal wall | Gypsum | 0.026 | 0.22 | 970 | 1090 |
| Linoleum / intermediate floor | Linoleum | 0.0025 | 0.156 | 1200 | 1260 |
| Linoleum / intermediate floor | Concrete | 0.3 | 1.7 | 2300 | 880 |
| Linoleum / intermediate floor | Acoustic tiles | 0.012 | 0.057 | 720 | 837 |
| Ground floor | Linoleum | 0.0025 | 0.156 | 1200 | 1260 |
| Ground floor | Concrete | 0.1 | 1.7 | 2300 | 880 |
| Ground floor | Expanded plastic | 0.1 | 0.035 | 1000 | 1700 |
| Roof above sixth floor | Acoustic tiles | 0.0125 | 0.057 | 720 | 837 |
| Roof above sixth floor | Concrete | 0.3 | 1.7 | 2300 | 880 |
| Roof above sixth floor | Mineral wool | 0.2 | 0.036 | 16 | 754 |
| Roof above sixth floor | Wood | 0.02 | 0.14 | 500 | 2300 |
| Roof above sixth floor | Under felt | 0.003 | 0.13 | 930 | 1300 |

Table 5.1 reports assembly U-values of 0.27 (long wall), **0.21** (short wall),
0.62 (internal wall), 1.75 (linoleum floor), 0.32 (ground floor), and 0.16 (roof).
Units are W/(m² K).

## Table 5.2 — PDF page 138 / printed page 136

| Element | Theoretical U, W/(m² K) | Applied U, W/(m² K) |
|---|---:|---:|
| External wall, long façade | 0.27 | 0.32 |
| External wall, short façade | 0.22 | 0.25 |
| Internal walls | 0.62 | 0.62 |
| Roof above sixth floor | 0.16 | 0.19 |
| Ground floor | 0.32 | 0.32 |
| Intermediate floors | 1.75 | 1.75 |

The accompanying text says initial IDA ICE 3.0 calculations omitted thermal
bridges; further calculations are described in Appendix E. Practical values
calculated according to Swedish Building Regulations were selected for the
reference simulation. The text also describes increasing wall and roof
insulation in the IDA ICE library. It says the envelope's total U·A does not
quite meet the regulation requirement, while heating energy meets the
regulations' reference-building requirement. This is a record of the source's
historical statements, not a present-day compliance assessment.

## Window evidence — Figure 5.10, PDF page 138 / printed page 136

Long-façade window: **type A**. Pasted figure labels are `sash`, `frame`,
`100 mm`, `1.3 m` and `1 m`; caption: typical window in the long façade.
The transcription does not establish which dimension belongs to which feature
or whether dimensions refer to the opening, frame or glazing. Retain these
labels without inferring pane construction, frame depth, glazing area or
thermal/optical properties. Check the figure image before building geometry.

Subsequent visual verification resolves the elevation dimensions: type A is
1.0 m wide by 1.3 m high, type B is 1.6 m wide by 2.7 m high. The 100 mm label
is the combined frame/sash sightline, not frame depth. Tables 5.3–5.4 give
glazing/frame areas of 0.88/0.42 m² for A and 3.5/0.82 m² for B; whole-window
U-values are 2.00 and 1.94 W/(m² K). Frames are wood with exterior aluminium.
The source describes three-pane units and a 30 mm intermediate blind space.
SHGC and VT remain unknown in these reviewed tables.

Appendix E's text on printed p.379 says insulation was reduced from 137 mm to
112.5 mm. Figure E.5 on p.380 displays 87 mm and U=0.317 W/(m² K).
Both were visually confirmed; neither overwrites the Table 5.1 recipe.

## Review items before office LoD2 implementation

- Keep long/short source stacks distinct in evidence. EPSM exports one wall:
  the dominant long-façade recipe calibrated to the weighted LoD1 target.
- Preserve theoretical and applied U-values separately. Do not force bridge-free
  layer calculations to equal applied values without an explicit adjustment model.
- Resolve the short-wall discrepancy: Table 5.1 says 0.21, Table 5.2 says 0.22.
- Check the long-wall wool/stud representation. Listed thicknesses alone do not
  establish parallel composite fractions or justify treating studs as a literal
  continuous serial layer.
- Verify the expanded-plastic density of **1000 kg/m³** against the PDF and
  source context. This value is retained exactly as supplied, not corrected.
- Review air-gap treatment separately from solid-material conductivity and
  carbon mappings; the tabulated values do not establish cavity ventilation.
- Check Appendix E and the insulation-adjustment context before claiming the
  listed recipes are the final simulated assemblies.
- Material links, property evidence, nominal exports and acceptance checks
  remain to be completed for this office LoD2 set.

## Implemented representative and accepted assumptions

The active JSON uses one EXT_WALL and one WINDOW. Original six opaque stacks,
material properties (including printed EPS density), source U-values remain in the archetype evidence. Original window geometry
is retained in this note; JSON exposes one representative window. No façade-specific domain
enums or active construction roles are needed.

Bounded thickness calibration fixes conductivities and selects the passing
candidate with least total change: 90 mm wall wool, 165 mm roof wool, two
25 mm partition gaps and a 160 mm intermediate slab. The ground stack keeps
its depths. These are representative nominal assemblies, not claims about the
final IDA ICE geometry. Original/adjusted mass and heat capacity are reported.
EPS density 20 kg/m³ is an accepted authoring assumption, not a thesis correction.

Figure 4.2 (printed p.102) directly describes the reference triple-clear system
with glazing g=0.691. Table H.1 (printed p.387) gives clear 4 mm pane visible
transmittance/reflection 0.893/0.082 for double-skin alternatives. Transferring
those pane properties to three identical reference panes is an assumption;
incoherent multiple reflections give glazing VT=0.725740. Zero frame optical
contribution and area-weighted A/B glazing fractions give representative
whole-window SHGC/VT=0.485721/0.510141. Intermediate blinds remain separate.

Pinned Boverket 02.07.000 links are reviewed generic/proxy families. Linoleum
uses a resilient rubber surrogate because the dataset lacks linoleum; acoustic
tiles assume a cement-bonded wood-wool family because chemistry is unspecified.
Those surrogate identities are not validated carbon factors. Absorptances
0.9/0.7/0.7 and MediumRough surfaces are reviewed authoring assumptions.

Catalogue LoD2 acceptance covers all 12 Existing office slots. Native Honeybee
and core handovers preserve nominal resistance, depth, mass and heat capacity.
Ground validation, complete carbon and full simulation readiness remain false;
the source plenum omission and other physical boundaries still need study.

## Original window records retained outside the archetype JSON

These are source observations used to derive one representative window, not
window variants in the EPSM archetype contract.

### Source A

```json
{
  "width_m": 1,
  "height_m": 1.3,
  "area_m2": 1.3,
  "glazing_area_m2": 0.88,
  "frame_area_m2": 0.42,
  "frame_sash_sightline_m": 0.1,
  "whole_window_u": 2,
  "glazing_u": 1.85,
  "frame_u": 2.31,
  "shgc": 0.4677538461538461,
  "vt": 0.491270394113725,
  "frame_description": "Wood with exterior aluminium cover",
  "glazing_description": "Three panes: 4 mm outer clear glass; 30 mm space; inner IGU described as D4-12. No full optical/gas specification inferred.",
  "shading": {
    "description": "White intermediate venetian blind in the 30 mm space",
    "slat_angle_degrees": 45,
    "glazing_u_with_blind": 1.65
  },
  "locator": "Table 5.3, printed p.137 / PDF p.139; Figure 5.10",
  "optics_basis": "Derived whole-window values: Figure 4.2 glazing SHGC; Table H.1 identical clear-4mm-pane VT transfer assumption; zero frame transmission."
}
```

### Source B

```json
{
  "width_m": 1.6,
  "height_m": 2.7,
  "area_m2": 4.32,
  "glazing_area_m2": 3.5,
  "frame_area_m2": 0.82,
  "frame_sash_sightline_m": 0.1,
  "whole_window_u": 1.94,
  "glazing_u": 1.85,
  "frame_u": 2.31,
  "shgc": 0.5598379629629628,
  "vt": 0.5879840838640175,
  "frame_description": "Wood with exterior aluminium cover",
  "glazing_description": "Three panes: 4 mm outer clear glass; 30 mm space; inner IGU described as D4-12. No full optical/gas specification inferred.",
  "shading": {
    "description": "White intermediate venetian blind in the 30 mm space",
    "slat_angle_degrees": 45,
    "glazing_u_with_blind": 1.65
  },
  "locator": "Table 5.4, printed p.138 / PDF p.140; Figure 5.11",
  "optics_basis": "Derived whole-window values: Figure 4.2 glazing SHGC; Table H.1 identical clear-4mm-pane VT transfer assumption; zero frame transmission."
}
```

Total source window area: 533 m²; area-weighted glazing fraction: 0.702925439511.
