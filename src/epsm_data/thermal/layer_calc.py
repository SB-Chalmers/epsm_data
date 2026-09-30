"""Layer-level thermal calculations.

Reports the existing homogeneous or area-weighted equivalent layer resistance.
"""

from __future__ import annotations

from dataclasses import dataclass

from epsm_data.domain.layer import Layer


@dataclass
class LayerThermalResult:
    """Calculation result for a single layer."""

    layer_code: str
    thickness: float
    is_composite: bool
    r_value: float  # m²·K/W
    u_value: float  # W/(m²·K)


def compute_layer_thermal(layer: Layer) -> LayerThermalResult:
    """Compute thermal resistance and transmittance for a layer.

    Parameters
    ----------
    layer : Layer
        Resolved construction layer.

    Returns
    -------
    LayerThermalResult
        Resistance in m² K/W and transmittance in W/(m² K).

    Notes
    -----
    Uses R = d / conductivity, with the existing area-weighted equivalent
    conductivity for composites. This is not a new standards implementation.
    """
    r = layer.r_value  # computation lives on the domain object
    return LayerThermalResult(
        layer_code=layer.layer_code,
        thickness=layer.thickness,
        is_composite=layer.is_composite,
        r_value=r,
        u_value=1.0 / r if r > 0 else float("inf"),
    )
