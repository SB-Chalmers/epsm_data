# Airflow inputs and units

Infiltration is an explicit envelope input. A stored rate always retains its
reference basis:

| Field | Unit | Basis |
| --- | --- | --- |
| `infiltration_l_s_m2` | L/(s m²) | `Atemp` or `conditioned_floor_area` |
| `infiltration_ach` | air changes/hour | `conditioned_volume` or `tabula_reference_volume` |

The catalogue's `EnvelopePerformance` records hold the accepted rate directly.
Unknown remains `None`; zero is a known zero. Mechanical ventilation and heat
recovery are separate system inputs.

Area-rate conversion to a particular building requires its matching area and
volume. A source-volume rate must retain its source reference volume convention;
it must not silently become model-volume ACH. The consuming application performs any necessary unit conversion explicitly.

Climate zones and fabric alternatives do not select ventilation topology. Core
and EPSM own applying rates to a building; completed runs should preserve the
actual rates, bases, areas and volumes used. Changes to accepted catalogue rates
are reviewed through a PR like other physical inputs.
