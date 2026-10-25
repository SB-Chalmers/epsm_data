# Ventilation and facade templates

Each archetype carries simple, explicit assumptions that `epsm_core` can apply to a
building when the building itself does not supply them.

## Ventilation

Any archetype can use any ventilation system. Pass the building's observed system,
for example its EPC ventilation type as resolved by epsm_db, and the archetype
returns the matching template; without it the era default below applies.

```python
archetype = catalogue.for_year("multi_family", 1970, state="existing", ventilation="FTX")
archetype.hvac_template          # epsm.ventilation.FTX_075
catalogue.ventilation_options("mf_se02", state="existing")  # S, F, FT, FTX templates
```

`hvac_template` is an airflow-only `HVACTemplate`. The platform merges airflow in
the order operating profile → template → envelope, so the profile keeps its
occupied ventilation rates and `envelope_performance` keeps infiltration.

| Template | Airflow |
| --- | --- |
| `epsm.ventilation.S` | Self-draught, 0.5 ACH (BBR 0.35 L/(s m²) at 2.5 m), no fans |
| `epsm.ventilation.F` | Mechanical exhaust, profile flow, no recovery |
| `epsm.ventilation.FT` | Supply and exhaust, profile flow, no recovery |
| `epsm.ventilation.FTX_060` / `_075` / `_080` | Supply and exhaust with heat recovery 0.60 / 0.75 / 0.80 |

**Observed system.** S, F and FT are used as observed. An observed FTX gets 0.75
in buildings before 1976 (it must be a retrofit), 0.60 in 1976–2005 (early original
recovery), 0.75 in 2006–2021 and 0.80 from 2022. Exhaust-air heat pumps are F
ventilation; the heat pump is a heating-system input.

**Era default**, used only when the building's system is unknown:

| Era | Single-family | Multi-family | Office | School |
| --- | --- | --- | --- | --- |
| SE.01 | S | S | S | S |
| SE.02 | S | F | FT | F |
| SE.03 | F | F | FT | FT |
| SE.04 | F | F | FTX 0.60 | FTX 0.60 |
| SE.05 | F | F | FTX 0.60 | FTX 0.60 |
| SE.06 | FTX 0.75 | FTX 0.75 | FTX 0.75 | FTX 0.75 |
| SE.07 | FTX 0.80 | FTX 0.80 | FTX 0.80 | FTX 0.80 |

Standard renovation keeps the existing (observed or default) system; Advanced
installs FTX 0.80. These are period assumptions from typical Swedish practice, not
measured stock shares. The rules live in
`src/epsm_data/datasets/standards/ventilation_templates.json`.

## Window-to-wall ratio

`catalogue.facade_assumptions(archetype_id)` returns a default ratio (window area /
gross facade area) and one value per facade orientation. A facade belongs to the
compass sector its outward normal faces: N 315–45°, E 45–135°, S 135–225°, W 225–315°.

| Type | Default | N | E | S | W | Basis |
| --- | --- | --- | --- | --- | --- | --- |
| Single-family | 0.18 | 0.12 | 0.17 | 0.26 | 0.17 | TABULA SE reference house |
| Multi-family | 0.24 | 0.22 | 0.23 | 0.28 | 0.23 | TABULA SE reference block |
| Office | 0.30 | 0.30 | 0.30 | 0.30 | 0.30 | EPSM assumption |
| School | 0.25 | 0.25 | 0.25 | 0.25 | 0.25 | EPSM assumption |

The four orientation values average to the default, so a building model may use
either form. Ratios are constant across eras and states. The values live in
`src/epsm_data/datasets/standards/facade_assumptions.json`.
