"""Element-level thermal calculations.

Applies boundary resistances, computes final U-value, and optionally compares
against a caller-selected reference.
"""

from __future__ import annotations

from dataclasses import dataclass

from epsm_data.domain.element import Element

from .boundary_conditions import get_boundary_resistances
from .component_calc import ComponentThermalResult, compute_component_thermal
from .standards import validate_against_reference


@dataclass
class ElementThermalResult:
    """Full thermal breakdown for an element."""

    element_name: str
    archetype: str
    application: str
    rsi: float  # m²·K/W
    rse: float  # m²·K/W
    r_total: float  # m²·K/W  (rsi + components + rse)
    u_value: float  # W/(m²·K)
    reference_u_value: float | None
    reference_warning: str | None
    component_results: list[ComponentThermalResult]


def compute_element_thermal(
    element: Element, *, reference_u_value: float | None = None
) -> ElementThermalResult:
    """Compute the full thermal profile for an element.

    Parameters
    ----------
    element : Element
        Opaque construction to evaluate.
    reference_u_value : float, optional
        Caller-selected reference in W/(m² K); no dataset is inferred.

    Returns
    -------
    ElementThermalResult
        Boundary resistances, component breakdown, and optional comparison.
    """
    rsi, rse = get_boundary_resistances(element.application)
    comp_results = [compute_component_thermal(c) for c in element.components]

    r_total = rsi + sum(cr.r_sum for cr in comp_results) + rse
    u_value = 1.0 / r_total if r_total > 0 else float("inf")

    return ElementThermalResult(
        element_name=element.name,
        archetype=element.archetype,
        application=element.application.value,
        rsi=rsi,
        rse=rse,
        r_total=r_total,
        u_value=u_value,
        reference_u_value=reference_u_value,
        reference_warning=validate_against_reference(u_value, reference_u_value),
        component_results=comp_results,
    )
