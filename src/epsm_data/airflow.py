"""Translate a reviewed matrix surcharge into a geometry-compatible Core rate.

References: TABULA CommonCalculationMethod, equation (7), printed pp.12–13 and
Table 4; packaged parametric/airflow_review.json. Sveby residential v2.0 chapters
5–6 distinguish normal-use ventilation and airing from envelope infiltration.
"""
from __future__ import annotations

import math


def infiltration_handoff(infiltration, *, reference_area_m2, conditioned_volume_m3):
    """Preserve source volumetric flow while changing the ACH reference volume.

    reference_area_m2 is TABULA A_C_ref or an explicitly documented building-area
    proxy. It is not silently inferred from Atemp. conditioned_volume_m3 must
    match Core's conditioned-zone volumes; exclude cold attics/unheated basements.
    This is unit/reference conversion, not a leakage measurement or fan-pressure
    model. Caller overrides without this source basis must not be converted.
    """
    for name, value in (("reference_area_m2", reference_area_m2),
                        ("conditioned_volume_m3", conditioned_volume_m3)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
    evidence = infiltration.evidence or {}
    basis = evidence.get("airflow_basis")
    if not basis or evidence.get("basis_stale"):
        raise ValueError("Reviewed, current source-volume evidence is required")
    if infiltration.unit != "1/h" or infiltration.value is None or not math.isfinite(infiltration.value) or infiltration.value < 0:
        raise ValueError("A finite nonnegative infiltration surcharge in 1/h is required")
    if basis["reference_volume"] != "tabula_reference_area_times_reference_height":
        raise ValueError("Unsupported infiltration reference volume")
    height = basis["reference_height_m"]
    reference_volume = reference_area_m2 * height
    flow_m3_h = infiltration.value * reference_volume
    return {
        "source_ach": infiltration.value,
        "reference_area_m2": reference_area_m2,
        "reference_height_m": height,
        "reference_volume_m3": reference_volume,
        "conditioned_volume_m3": conditioned_volume_m3,
        "additional_flow_m3_s": flow_m3_h / 3600,
        "additional_flow_l_s_per_reference_m2": infiltration.value * height / 3.6,
        "core_envelope_infiltration_ach": flow_m3_h / conditioned_volume_m3,
        "review_id": basis["review_id"],
        "status": "reference_volume_converted_engineering_assumption",
        "pressure_coupling": basis["pressure_coupling"],
    }
