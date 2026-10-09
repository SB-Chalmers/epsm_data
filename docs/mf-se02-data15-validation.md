# Completed MF SE.02 Data 1.5 validation

The 2026-10-05 completed rerun covers 85 buildings in 54 Gothenburg properties:
existing MF SE.02, exhaust ventilation F, district heat, normal-use-adjusted
annual delivered space heating excluding DHW. Weather uses the actual year.

| Held-out metric | Data 1.5 baseline | Fold-dependent selection procedure |
| --- | ---: | ---: |
| Within 20% | 54/85 | 55/85 |
| Within 10% | 37/85 | 40/85 |
| MAE, kWh/m²/year | 14.302 | 14.337 |
| Signed bias, kWh/m²/year | +4.079 | +4.629 |

Three outer folds selected baseline; two selected shared corrections. Final
all-property inner validation selected **baseline**, with **no fitted overrides**.
Thus the current catalogue keeps additional infiltration 0.20 L/s/m² Atemp,
window U 2.2 W/(m² K), and designed ventilation 0.35 L/s/m² Atemp. These remain
provisional assumptions rather than measured properties.

The method fitted from one representative property repeatedly chose infiltration
multiplier 0.5 but transferred poorly: only 38/85 within 20%. Annual heating responses
for infiltration, ventilation, window heat loss, setpoint and solar gain are
confounded; sensitivity does not identify actual component values. There is no
basis for another universal infiltration or window adjustment from this study.

Both numerical failures remain in accuracy denominators. The 30 misses of the
selection procedure comprise 24 overpredictions, four underpredictions and two
failures across 17 properties. Priorities are EPC metering/Atemp allocation,
renovation history, ventilation/operation, heated basement extent and verified
shared walls. These diagnoses do not alter the frozen evaluation.

Current profile: [v2](../cohort_profiles/2026-10-05-v2/README.md).
The historical ACH-based v1 profile is superseded, retained for provenance.
Packaged evidence: [mf_se02_data15_validation.json](../src/epsm_data/datasets/parametric/mf_se02_data15_validation.json),
including source hashes, exact metrics and final selection. Workflows campaign:
`cohort-transfer-mf-se02-parent-data15-2026-10-04-v11`.

This is retrospective property cross-validation on previously inspected
observations. It does not establish national accuracy or independent support for
other eras, uses, renovation states or ventilation/heating systems. Accuracy target
not met; status remains provisional. Numeric catalogue values and package/database
versions are retained; this update records completed evidence and current profile.
