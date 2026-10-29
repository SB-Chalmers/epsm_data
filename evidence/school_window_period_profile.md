# School whole-window period profile

## Current catalogue interpretation, reviewed 2026-10-24

The original nine-period values and six-era averaging below are retained as
authoring evidence. The current catalogue has SE.06 for **2006–2021** and a
single SE.07 configuration beginning in **2022**. Its numerical values are:

| Current EPSM era | Existing/default Uw | Standard Uw | Advanced Uw |
| --- | ---: | ---: | ---: |
| SE.01 | 2.80 | 1.22 | 0.90 |
| SE.02 | 2.70 | 1.22 | 0.90 |
| SE.03 | 2.25 | 1.22 | 0.90 |
| SE.04 | 1.90 | 1.22 | 0.90 |
| SE.05 | 1.60 | 1.22 | 0.90 |
| SE.06 | 24/21 ≈ 1.142857 | 1.08 | 0.90 |
| SE.07 | 0.90 | not applicable | not applicable |

These are explicit retained representative whole-window choices. The SE.06
existing value inherits the earlier 2006–2026 numerical snapshot; it is **not**
recalculated or claimed as an equal-year mean for the new 2006–2021 bin. Current
modern standard/advanced values and SE.07 are modelling assumptions, not
observed stock averages or a building-code acceptance claim. The current
standard replacement definition is 1.22 rather than a literal 1.20 request.
No window value has been retuned to reduce an annual heating gap.

Revised 2026-10-25: the former generic whole-window SHGC 0.70 / VT 0.75
(existing) and 0.50 / 0.65 (standard/advanced) exceeded what a framed window can
transmit. Existing optics now use TABULA glazing g by pane count (Uw >= 2.2
two-pane g 0.8; 1.6-2.2 three-pane g 0.7; below 1.6 low-e g 0.6), glass LT 0.75
and frame fraction 0.30. Standard replacements follow the Elitfönster Uw
1.10-1.22 options (LT 0.75, g 0.60). Advanced Uw 0.9 now reuses the TABULA
Wood 3p replacement window. The U curve above is unchanged. These whole-window
values must not receive another frame-area conversion. See the [current recipe contract](nonresidential_current_recipe_contract.md).

## Retained source profile and original interpretation

The period values below were supplied by the user on 2026-09-22 from another
EPSM school model. The original model export, derivation and stock weighting were
not provided. They are representative modelling inputs, not measured Swedish
school-stock averages or window values taken from PUB-003, PUB-010, PUB-277 or
PUB-611. Construction is invariant across the model's BBR19 Zones I–III.

| Construction period | Existing whole-window Uw, W/(m²K) |
| --- | ---: |
| Before 1945 | 2.80 |
| 1945–1960 | 2.80 |
| 1961–1970 | 2.80 |
| 1971–1980 | 2.50 |
| 1981–1990 | 2.00 |
| 1991–2000 | 1.80 |
| 2001–2010 | 1.40 |
| 2011–2020 | 1.10 |
| 2021–2026 | 1.00 |

The supplied scenario description gives Standard window Uw 1.2 and Advanced
window Uw 0.9 for older buildings. We interpret *older* as construction through
2010. The 2011–2026 window values remain unchanged in both scenarios. This
cutoff is a modelling choice because the source description did not define
"older" precisely.

### Original mapping to six EPSM eras

When an EPSM era crosses source periods, each construction year receives equal
weight. This is not a claim about numbers of schools constructed in each year.
The original six-era target interpretation was:

| EPSM era | Existing | Standard | Advanced | Overlap calculation |
| --- | ---: | ---: | ---: | --- |
| SE.01 (to 1960) | 2.80 | 1.20 | 0.90 | Both source periods before 1961 have the same Uw. |
| SE.02 (1961–1975) | 2.70 | 1.20 | 0.90 | `(10×2.8 + 5×2.5)/15` |
| SE.03 (1976–1985) | 2.25 | 1.20 | 0.90 | `(5×2.5 + 5×2.0)/10` |
| SE.04 (1986–1995) | 1.90 | 1.20 | 0.90 | `(5×2.0 + 5×1.8)/10` |
| SE.05 (1996–2005) | 1.60 | 1.20 | 0.90 | `(5×1.8 + 5×1.4)/10` |
| SE.06 (2006–present) | 24/21 ≈ 1.143 | 23/21 ≈ 1.095 | 21.5/21 ≈ 1.024 | Fixed 2006–2026 snapshot: 5 years at 2001–2010 values, 10 at 2011–2020 values and 6 at 2021–2026 values. |

This original interpretation treated SE.06 as open ended. It is retained as
history after the current era split and must not be used to claim that the
current modern states reproduce this old averaging rule. It did not establish
performance for construction outside the supplied 2006–2026 rows.

The existing catalogue's optional generic window guardrail has a nominal
1.0 W/(m²K) lower bound. Explicit Advanced overrides retain the supplied 0.9
target for SE.01–SE.05, with the exception visible in property guardrail evidence.
No other category's window curve or guardrail is changed.

The separate PUB-003 Gävle case school reports Uw 2.7 for its observed 1960s
condition. Its agreement with the SE.02 equal-year period value does not verify
the nine-period profile. The PUB-611 Fridhemsskolan Hus 1 window reports Uw 1.9;
its construction year and representativeness for SE.04 remain unverified, so it
is not used to date the curve.
