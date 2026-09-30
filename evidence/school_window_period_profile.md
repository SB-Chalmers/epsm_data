# School whole-window period profile

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

## Mapping to the six EPSM eras

When an EPSM era crosses source periods, each construction year receives equal
weight. This is not a claim about numbers of schools constructed in each year.
The six era/state targets stored in `school.window` are:

| EPSM era | Existing | Standard | Advanced | Overlap calculation |
| --- | ---: | ---: | ---: | --- |
| SE.01 (to 1960) | 2.80 | 1.20 | 0.90 | Both source periods before 1961 have the same Uw. |
| SE.02 (1961–1975) | 2.70 | 1.20 | 0.90 | `(10×2.8 + 5×2.5)/15` |
| SE.03 (1976–1985) | 2.25 | 1.20 | 0.90 | `(5×2.5 + 5×2.0)/10` |
| SE.04 (1986–1995) | 1.90 | 1.20 | 0.90 | `(5×2.0 + 5×1.8)/10` |
| SE.05 (1996–2005) | 1.60 | 1.20 | 0.90 | `(5×1.8 + 5×1.4)/10` |
| SE.06 (2006–present) | 24/21 ≈ 1.143 | 23/21 ≈ 1.095 | 21.5/21 ≈ 1.024 | Fixed 2006–2026 snapshot: 5 years at 2001–2010 values, 10 at 2011–2020 values and 6 at 2021–2026 values. |

SE.06 remains a single open-ended catalogue era. Its snapshot is valid as a
representative choice for the supplied 2006–2026 rows; it does not establish
performance for later construction. A future catalogue revision can split the
modern era or replace the snapshot when newer evidence is available.

The existing catalogue's optional generic window guardrail has a nominal
1.0 W/(m²K) lower bound. Explicit Advanced overrides retain the supplied 0.9
target for SE.01–SE.05, with the exception visible in property guardrail evidence.
No other category's window curve or guardrail is changed.

The separate PUB-003 Gävle case school reports Uw 2.7 for its observed 1960s
condition. Its agreement with the SE.02 equal-year period value does not verify
the nine-period profile. The PUB-611 Fridhemsskolan Hus 1 window reports Uw 1.9;
its construction year and representativeness for SE.04 remain unverified, so it
is not used to date the curve.
