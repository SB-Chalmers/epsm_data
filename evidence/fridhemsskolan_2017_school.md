# Fridhemsskolan: published and provisional school layers

PUB-611 is Fayad Abdalla Mohamed Ahmed (2017), *Energy Audit in Educational
Buildings: Case Study of Fridhemsskolan in Gävle*, a University of Gävle student
thesis, Master degree (one year), 15 HE, Energy Systems. **No DOI is assigned.**
[Public DiVA PDF](https://www.diva-portal.org/smash/get/diva2%3A1139939/FULLTEXT01.pdf).
The user's Linux PUB-611 PDF and catalogue-markdown paths were unavailable on
this Mac. The public PDF was inspected instead: Table 3-1 (printed p.19 / PDF
p.28), p.20 / PDF p.29, and Appendix Figures 8-11 to 8-14 (pp.56-57).

PUB-003 is a separate peer-reviewed paper, Steen Englund et al. (2020),
*Measured and Simulated Energy Use in a Secondary School Building in Sweden -
A Case Study of Validation, Airing, and Occupancy Behaviour*, DOI
[10.3390/en13092325](https://doi.org/10.3390/en13092325). Its existing school
opaque LoD1 anchors are not overwritten or attributed to PUB-611. The 2.7
window target now comes from the separately documented school period profile;
it numerically agrees with the PUB-003 window input.

## One representative and source corrections

The user selected **Hus 1/3**. The alternative `school_fridhem` Existing state has one
external wall, roof, ground floor, partition, intermediate floor and window.
The window uses the dominant Hus 1 source system; there is no Hus 3 window
variant in the JSON contract. Year 1960 and the SE.02 assignment are provisional
catalogue conventions, not a verified construction date for Fridhemsskolan.

Visual inspection resolves a merged-row transcription issue: the **23 mm wood
row belongs to the roof**, not the Hus 1/3 external wall. Table 3-1 lists four
wall layers. Figure 8-11 explicitly labels their list inside to outside. Its
IDA ICE screenshot reports U=0.1568, different from Table 3-1's 0.17. Any added
wood wall cladding is a modelling hypothesis, not a published fifth layer.

Roof Table 3-1 ends with gypsum followed by the 28 mm framing zone; Figure 8-12
shows framing followed by gypsum and U=0.1365 rather than the table's 0.15.
The JSON retains table order, records the disagreement and marks the assumed
wood-outside physical orientation provisional. The printed conductivity typo
`0..22` for roof gypsum is interpreted as 0.22 and documented here.

## Published opaque layers

Conductivity is W/(m K); depths are mm. The source supplies conductivity but
not density, specific heat or absorptances. Those added properties are
**provisional numerical proxies**, including for rows whose depths are published.

| Assembly | Table sequence | Source U, W/(m2 K) |
|---|---|---:|
| Hus 1/3 wall | Gypsum 25 (0.22); wool 190 (0.036); gypsum 9.5 (0.22); framing/insulation equivalent 34 (0.044) | 0.17 |
| Hus 1/3 roof | Wood 23 (0.14); air 45 (0.25); chipboard 3.2 (0.13); wool 220 (0.036); gypsum 12.5 (0.22); framing/insulation equivalent 28 (0.044) | 0.15 |
| Ground floor | Concrete 100 (1.7); Cellplast 80 (conductivity missing); macadam 150 (0.2) | 0.31 |

EPS identity, lambda=0.035, density=20 and cp=1700 are assumed for Cellplast.
Framing zones retain source lambda=0.044, with provisional density=80 and
cp=1000. They are homogeneous numerical equivalents; no real stud fractions,
steel/timber species or spacing are established. Density/capacity of other
materials and MediumRough surfaces with absorptances 0.9/0.7/0.7 are proxies.
Macadam remains numerical layer evidence, not a validated ground boundary.

## Provisional layers retained explicitly

- Wall: add 23 mm exterior wood cladding as **provisional** weather-side finish.
  Reverse only the four published wall rows for EPSM outside-to-inside order.
- Partition: 13 mm gypsum + 95 mm homogenized stud/wool zone + 13 mm gypsum.
  The supplied range was 70-95 mm; 95 mm is a selected hypothesis, not evidence.
- Intermediate floor: 2.5 mm assumed linoleum finish + 60 mm screed/topping +
  225 mm concrete slab + 150 mm equivalent ceiling cavity + 13 mm gypsum.
  The user supplied topping/slab ranges of 50-70 / 200-250 mm. The exact finish
  and 150 mm cavity depth are additional assumptions; cavity physics is unvalidated.
- Detailed window: low-E 4 + argon 16 + clear glass 4 + argon 16 + low-E 4 mm,
  with wood or wood/aluminium frame. **Every detailed glazing layer and frame
  specification is provisional.** The exported window is one simple whole-window
  system; these inferred pane layers are metadata, not validated gas/coating data.
- Hus 2 basement: interior finish, 200-250 mm concrete/lightweight-concrete wall,
  waterproofing/drainage, 100-150 mm EPS/mineral wool and backfill. This remains
  an **inactive provisional hypothesis**, not a construction in Hus 1/3.

## Window evidence and one numerical system

Printed p.20 reports **Hus 1 and Hus 2: three panes, U=1.9, SHGC=0.68, solar
transmittance=0.6**. It separately reports **Hus 3: two panes, U=2.9, SHGC=0.76,
solar transmittance=0.7**. Those source observations remain here, not separate
window types in the archetype JSON.

Use one Hus 1 numerical representative with U=1.9 and SHGC=0.68. These reported
window values are adopted for the whole-window slot; a frame/glazing thermal
breakdown is unknown. **VT=0.65 is provisional. Solar transmittance=0.6 is not VT.**
Low-E coatings, argon fill and frame identity are not validated by the thesis.

## Hus 2 differences retained as inactive source evidence

Table 3-1 wall rows are wood 23, air 45, framing/insulation 45, gypsum 9.5,
wool 190, gypsum 12.5 and Protect F 15.4 mm, with U=0.14. Protect F conductivity
is reported as 0.7; its material identity remains unknown. The roof includes
both 28 and 45 mm framing zones and wool 270 mm, with U=0.102. The ground stack
is the same. Figure 8-14 differs in roof air-gap/order details; it reports
U=0.1023. The thesis identifies a basement classroom but not its wall build-up.

## Coverage, acceptance and exports

This is an earlier unassigned alternative to the canonical School SE.02 recipe;
it contributes no current portable catalogue slots. The historical authoring
workflow reported coverage **864/1080** after its MF, SF, Office and canonical
School completions. Those historical counters are not the current portable
catalogue's 28 archetypes/76 configurations/228 climate assignments. The Fridhem
draft has open provisional-property, mapping and source-selection review items
and is **not accepted as a canonical period representative**.

The earlier school LoD1 targets used PUB-003 for wall 0.32, roof 0.15 and ground 0.22;
the period profile supplies window 2.7. Internal wall 1.271 and intermediate floor
2.190288 are office proxies. PUB-003's ground
value has an effective-ground interpretation. Fridhem source and layer-only
values are stored separately; no thickness is tuned to this different reference.

Honeybee and core nominal handovers preserve depth, resistance, mass/capacity
and reciprocal order. They carry draft/provisional labels. Native parser success
means a payload can be read; it does not establish that inferred assemblies,
optics, ground heat transfer or carbon are source-validated. The portable JSON
retains detailed assembly annotations. No renovated Fridhem states are inferred;
canonical current period choices and their limits are documented in
[the current recipe contract](nonresidential_current_recipe_contract.md).
