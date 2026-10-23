"""Explicit reference-volume conversion for declared envelope infiltration."""

import math

from .domain import EnvelopePerformance


def infiltration_handoff(
    infiltration, *, reference_area_m2, conditioned_volume_m3, reference_height_m
):
    """Conserve flow when converting declared source-volume ACH to Core.

    Reference height is an explicit convention, not a measured storey height.
    Geometry and area interpretation remain caller choices.
    """
    if not isinstance(infiltration, EnvelopePerformance):
        raise TypeError("infiltration must be an EnvelopePerformance")
    if infiltration.infiltration_reference_basis != "tabula_reference_volume":
        raise ValueError("Expected tabula_reference_volume infiltration")
    rate = infiltration.infiltration_ach
    if rate is None:
        raise ValueError("A known source infiltration rate is required")
    for name, value in (
        ("reference_area_m2", reference_area_m2),
        ("conditioned_volume_m3", conditioned_volume_m3),
        ("reference_height_m", reference_height_m),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError(f"{name} must be finite and positive")
    volume = reference_area_m2 * reference_height_m
    flow = rate * volume
    return {
        "source_ach": rate,
        "reference_area_m2": reference_area_m2,
        "reference_height_m": reference_height_m,
        "reference_volume_m3": volume,
        "conditioned_volume_m3": conditioned_volume_m3,
        "additional_flow_m3_s": flow / 3600,
        "additional_flow_l_s_per_reference_m2": rate * reference_height_m / 3.6,
        "core_envelope_infiltration_ach": flow / conditioned_volume_m3,
    }
