# Airflow inputs and units

The current MF additional infiltration assumptions use **L/(s m² Atemp)**. They remain engineering assumptions with their source and limitations attached to each current property. Mechanical ventilation is a separate input.

| Period | Existing | Standard | Advanced |
| --- | ---: | ---: | ---: |
| SE.01–SE.02 | 0.20 | 0.10 | 0.10 |
| SE.03–SE.04 | 0.10 | 0.10 | 0.05 |
| SE.05–SE.06 | 0.10 | 0.10 | 0.025 |

SE.07 has one independent configuration copied from SE.06 Advanced, including 0.025 L/(s m² Atemp). Its values do not change when SE.06 is edited. The construction-year boundary is 2022.

These leakage values do not vary with the S/F/FT/FTX classification. FTX recovery applies to mechanical ventilation, not infiltration. Exhaust pressure coupling remains an unresolved modelling assumption. Sveby ventilation guidance does not establish these infiltration rates.

For Core's area-rate input, set `envelope_infiltration_ach=0` and `envelope_infiltration_l_s_m2=q`, and supply Atemp explicitly as the load reference area. The compatibility ACH representation is `q * 3.6 / 2.5`, based on the source reference height. It must not be applied to a different actual volume without conversion.

Other categories retain their recorded source convention. `epsm_data.airflow.infiltration_handoff` requires current source-volume evidence and returns the explicit conversion; unsupported or stale source bases are rejected.

Current source records are `datasets/parametric/airflow_review.json`, `mf_airflow_starting_values.json`, and the effective-property evidence in `catalogue.json`. Historical validation outputs and calibrated cohort experiments belong to Studies. A new property selection should record its own physical evidence and preserve the actual inputs used in any completed study.
