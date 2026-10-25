# Current nonresidential recipe contract

Reviewed 2026-10-24. This is the current portable catalogue contract for
Office and School SE.01–SE.07. The retained nine-period user stack notes are
source instructions and authoring history. Their exact quantities are not a
claim that every current six-era/state recipe implements every earlier item.
This note states the current choices without changing layers to match a target
U-value, annual heating output or residential benchmark.

## Current representatives

The catalogue has 19 physical configurations per category: existing, standard
and advanced in SE.01–SE.06 and one SE.07 default. SE.06 is 2006–2021; SE.07
starts in 2022. Climate-zone assignments share the same physical construction.
Year ranges select representative families, not verified as-built conditions or
stock-weighted national means. Each baseline/default has a source-limited
plausibility rationale, which does not close the independent source,
constructability or material-property reviews.

School SE.01 uses masonry and a suspended timber ceiling above an unheated
basement. Later school periods use representative timber-frame walls and
concrete/insulation slab families. All school thermal tops are cold-attic
ceilings. Office SE.01 has the old masonry/cold-attic family; later offices use
compact roofs and their retained concrete families. The concrete intermediate
floor/acoustic lining and old heavy-fill timber intermediate floor are explicit
engineering defaults. Their transfer to schools is an analogy, not evidence of
school-stock prevalence. See `intermediate_floor_extraction_review.json`.

The inherited nonstandard partition core depths remain visible pending a
product-depth rationale. Adding era notes does not verify those dimensions or
turn a generic proxy into a historical product. Registered thermal properties,
density and heat capacity remain numerical proxies where source-specific
measurements are absent.

### Soil slab and suspended ceiling are separate

Office and School SE.01 declare `foundation_context = unheated_basement` as the
source representative context. `GROUND_FLOOR` is the conditioned floor above
that basement: its lower-room-to-upper-room placement is the retained
plaster/boards/timber-infill/floorboards assembly. It is not a soil slab.
`BASEMENT_FLOOR` is a distinct 100 mm concrete soil-contact slab from the
supplied P01 recipe. It uses the existing registered concrete properties; no
soil correction is embedded in its layers. Both remain unchanged through the
current standard/advanced packages. The thin damp-proofing and gravel subbase
remain omitted functional details, not a fixed soil temperature or added
resistance fitted to a reference U-value.

Core must select the explicit soil slab at the physical bottom, including a
caller-selected no-basement model. With a basement, the suspended
`GROUND_FLOOR` remains the internal interface and `BASEMENT_FLOOR` belongs at
soil. A no-basement model is an explicit project alternative using the soil
slab, not a claim that the source representative lacked a basement. Basement
conditioning, dimensions, wall/plinth exposure, soil and solver remain project
inputs. Source-prescribed basement retrofit packages are not installed merely
because these reusable roles exist.

### Thermal top and weather shell are separate

Cold-attic configurations explicitly assign `TOP_FLOOR` to the conditioned
thermal ceiling and `ROOF` to the retained thin timber/bituminous weather shell
identified by `weather_shell_element_id`. The shell is an explicit generic
completion, not a measured historic roof or a second conditioned thermal roof.
Compact office configurations retain their `ROOF` construction; Core may use
that role for a generated conditioned top when no `TOP_FLOOR` is supplied. Such
an alias must not replace a cold-attic ceiling with its weather shell.

### Intermediate-floor order

The supplied intermediate-floor sequence is upper-room finish to lower-room
soffit. Canonical nonresidential `INTERMEDIATE_FLOOR` elements are now stored in
bottom-to-top order, equivalent to outside-to-inside for the upper floor face.
The lower ceiling is its reciprocal reversed construction. Component order and
layer positions are reversed together; thickness, resistance and total
mass/capacity are unchanged. `source_sequence` retains the original authored
component IDs, and state metadata records the original upper-to-lower order.
Residential and caller-authored/custom constructions are not normalized by this
nonresidential catalogue correction.

## Current renovations

The current named packages are representative authoring scenarios. They retain
baseline fabric except for their explicit wall/top overlays, window choice and
airtightness value. They do not imply observed renovation history, an installed
HVAC system or a universal intervention at the construction year.

School SE.01–SE.06 currently add 100/200 mm facade board and 150/200 mm attic
wool for standard/advanced respectively. These common packages differ from the
earlier varying nine-period additions. The old notes' basement EPS, ceiling
wool/fire-lining and recent-building unchanged-fabric instructions are retained
as source history; the current default keeps basement assemblies unchanged and
does not infer excavation or a suspended-floor retrofit. An actual intervention
requires an explicit project selection. Office packages are the current
registered overlays summarized by the forward U-values below, not a promise of
literal equality to every earlier period-note quantity.

SE.07 adopts the current SE.06 advanced physical family as an explicit new-build
representative, without creating renovation alternatives. This is not an
observed 2022+ stock average, code-compliance claim or instruction to retrofit a
new building. Modern school windows are inherited representative numerical
choices; their values are not recomputed from an obsolete open-ended SE.06 bin.

### Windows and optics

The original school window profile records user-supplied whole-window U-values
and an equal-construction-year averaging convention. Its original model export
and stock weights were not provided. The old six-era SE.06 averaging included
2006–2026; it is source history after the era split. Current SE.06 and SE.07
values in the table below are explicit retained modelling choices. Standard
school U=1.22 for SE.01–SE.05 is the retained numerical replacement definition,
not an exact transcription of the earlier U=1.20 request. The modern current
values and their source limits are detailed in `school_window_period_profile.md`.

SHGC and visible transmittance are whole-window values derived as glazing g and
light transmittance times (1 - frame fraction 0.30). Office existing optics
follow the Poirazis (2008) derivation. School existing optics use TABULA glazing
g by pane count (two-pane 0.8, three-pane 0.7, low-e 0.6 with glass LT 0.75);
modern replacements use Swedish triple low-e glass (Elitfönster, LT 0.74,
g 0.53) or the TABULA Wood 3p replacement at Uw 0.9. Each window's provenance is
stored with its thermal record. They are not validated school-stock optics. Do not apply another frame-area multiplier to
these whole-window values. A reduction in SHGC can offset some winter heating
savings, especially when the original envelope is already insulated.

### Forward nominal values

Values are W/(m² K), computed from stored nominal layers and declared films.
The ground column is the lowest conditioned-floor construction; for SE.01 it
is the suspended basement ceiling. It is not an effective ground coefficient.
The separate SE.01 soil slab has one 100 mm concrete layer and requires the
chosen soil/geometry method. No value below is a measured energy benchmark.

| Configuration | State | Wall U | Thermal top U | Ground-role U | Window U | SHGC / VT |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Office SE.01 | existing | 1.2594 | 0.4641 | 0.3131 | 2.8 | 0.49 / 0.51 |
| Office SE.01 | standard | 0.2615 | 0.1746 | 0.3131 | 1.22 | 0.42 / 0.53 |
| Office SE.01 | advanced | 0.1600 | 0.1076 | 0.3131 | 0.9 | 0.35 / 0.52 |
| Office SE.02 | existing | 0.5993 | 0.3639 | 0.6036 | 2.8 | 0.49 / 0.51 |
| Office SE.02 | standard | 0.2128 | 0.1494 | 0.6036 | 1.22 | 0.42 / 0.53 |
| Office SE.02 | advanced | 0.1404 | 0.1072 | 0.6036 | 0.9 | 0.35 / 0.52 |
| Office SE.03 | existing | 0.3997 | 0.2936 | 0.6036 | 2.8 | 0.49 / 0.51 |
| Office SE.03 | standard | 0.1808 | 0.1360 | 0.6036 | 1.22 | 0.42 / 0.53 |
| Office SE.03 | advanced | 0.1257 | 0.1057 | 0.6036 | 0.9 | 0.35 / 0.52 |
| Office SE.04 | existing | 0.3411 | 0.2384 | 0.4053 | 2.3595 | 0.49 / 0.51 |
| Office SE.04 | standard | 0.1677 | 0.1228 | 0.4053 | 1.22 | 0.42 / 0.53 |
| Office SE.04 | advanced | 0.1192 | 0.1057 | 0.4053 | 0.9 | 0.35 / 0.52 |
| Office SE.05 | existing | 0.2243 | 0.1815 | 0.3226 | 1.98829 | 0.49 / 0.51 |
| Office SE.05 | standard | 0.1335 | 0.1057 | 0.3226 | 1.22 | 0.42 / 0.53 |
| Office SE.05 | advanced | 0.1009 | 0.0928 | 0.3226 | 0.9 | 0.35 / 0.52 |
| Office SE.06 | existing | 0.1749 | 0.1465 | 0.1751 | 1.3 | 0.49 / 0.51 |
| Office SE.06 | standard | 0.1143 | 0.0928 | 0.1751 | 1.22 | 0.42 / 0.53 |
| Office SE.06 | advanced | 0.0895 | 0.0827 | 0.1751 | 0.9 | 0.35 / 0.52 |
| Office SE.07 | default | 0.0895 | 0.0827 | 0.1751 | 0.9 | 0.35 / 0.52 |
| School SE.01 | existing | 1.5435 | 0.4641 | 0.3131 | 2.8 | 0.56 / 0.53 |
| School SE.01 | standard | 0.2719 | 0.1746 | 0.3131 | 1.22 | 0.42 / 0.53 |
| School SE.01 | advanced | 0.1491 | 0.1446 | 0.3131 | 0.9 | 0.35 / 0.52 |
| School SE.02 | existing | 0.4598 | 0.3012 | 0.6036 | 2.7 | 0.56 / 0.53 |
| School SE.02 | standard | 0.1921 | 0.1451 | 0.6036 | 1.22 | 0.42 / 0.53 |
| School SE.02 | advanced | 0.1214 | 0.1237 | 0.6036 | 0.9 | 0.35 / 0.52 |
| School SE.03 | existing | 0.3289 | 0.2335 | 0.4551 | 2.25 | 0.56 / 0.53 |
| School SE.03 | standard | 0.1647 | 0.1273 | 0.4551 | 1.22 | 0.42 / 0.53 |
| School SE.03 | advanced | 0.1099 | 0.1106 | 0.4551 | 0.9 | 0.35 / 0.52 |
| School SE.04 | existing | 0.2840 | 0.1808 | 0.3324 | 1.9 | 0.49 / 0.53 |
| School SE.04 | standard | 0.1526 | 0.1099 | 0.3324 | 1.22 | 0.42 / 0.53 |
| School SE.04 | advanced | 0.1044 | 0.0971 | 0.3324 | 0.9 | 0.35 / 0.52 |
| School SE.05 | existing | 0.2499 | 0.1475 | 0.2294 | 1.6 | 0.49 / 0.53 |
| School SE.05 | standard | 0.1422 | 0.0966 | 0.2294 | 1.22 | 0.42 / 0.53 |
| School SE.05 | advanced | 0.0994 | 0.0866 | 0.2294 | 0.9 | 0.35 / 0.52 |
| School SE.06 | existing | 0.1889 | 0.0989 | 0.1416 | 1.14286 | 0.42 / 0.53 |
| School SE.06 | standard | 0.1201 | 0.0731 | 0.1416 | 1.08 | 0.42 / 0.53 |
| School SE.06 | advanced | 0.0881 | 0.0673 | 0.1416 | 0.9 | 0.35 / 0.52 |
| School SE.07 | default | 0.0881 | 0.0673 | 0.1416 | 0.9 | 0.35 / 0.52 |

## Scope of acceptance

A nonresidential normal-use model needs an explicitly declared Atemp, calendar,
active dates, zone-use/role allocation, HVAC topology, ventilation/recovery and
infiltration conversion. Era does not select historical operation. Bridge
uplift is a project input; multiplicative Core material uplift is not the
additive TABULA bridge convention. Slab/buried-wall nominal U must not be
compared directly with an already ground-effective source U.

Known carbon modules remain separate from missing A4/A5 or partial A5.1.
Retained old shavings without compatible carbon factors are unknown existing
stock, not zero-carbon new material. Adding the soil slab does not manufacture
missing lifecycle factors. Successful parser, schema or engine checks do not
establish historical prevalence, construction compliance, measured-energy
accuracy or complete LCA.

Fridhemsskolan remains source-specific evidence and an earlier provisional
alternative, not a canonical period validation. Its thesis-supplied depths and
window observations must be distinguished from inferred densities, capacity,
framing fractions and detailed glazing assumptions.
