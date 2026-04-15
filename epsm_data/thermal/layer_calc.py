"""Layer-level thermal calculations.

Computes thermal resistance for homogeneous and composite layers
using area-weighted lambda/U-value averaging per SS-EN ISO 6946.
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

    For single-material layers: R = d / λ.
    For composite layers: weighted average of lambda-method and
    U-value-method (ISO 6946 §6.4.2).
    """
    r = layer.r_value  # computation lives on the domain object
    return LayerThermalResult(
        layer_code=layer.layer_code,
        thickness=layer.thickness,
        is_composite=layer.is_composite,
        r_value=r,
        u_value=1.0 / r if r > 0 else float("inf"),
    )
