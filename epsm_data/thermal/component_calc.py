"""Component-level thermal calculations.

Aggregates layer R-values into a component total and provides a
per-layer breakdown.
"""

from __future__ import annotations

from dataclasses import dataclass

from epsm_data.domain.component import Component

from .layer_calc import LayerThermalResult, compute_layer_thermal


@dataclass
class ComponentThermalResult:
    """Calculation result for a component (ordered layer stack)."""

    component_name: str
    archetype: str
    shearing_layer: str
    total_thickness: float  # m
    r_sum: float  # m²·K/W  (no boundary resistances)
    layer_results: list[LayerThermalResult]


def compute_component_thermal(component: Component) -> ComponentThermalResult:
    """Sum layer resistances for a component and return per-layer breakdown."""
    layer_results = [compute_layer_thermal(layer) for layer, _ in component.layers]
    return ComponentThermalResult(
        component_name=component.name,
        archetype=component.archetype,
        shearing_layer=component.shearing_layer.value,
        total_thickness=component.thickness,
        r_sum=component.r_sum,
        layer_results=layer_results,
    )
