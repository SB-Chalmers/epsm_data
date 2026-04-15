"""Thermal calculation engine.

Single source of truth for all R/U-value calculations across layers,
components, and elements.
"""

from .boundary_conditions import (
    RSE_EXTERIOR,
    RSE_INTERIOR,
    RSI_DEFAULT,
    get_boundary_resistances,
    get_rse,
    get_rsi,
)
from .component_calc import ComponentThermalResult, compute_component_thermal
from .element_calc import ElementThermalResult, compute_element_thermal
from .layer_calc import LayerThermalResult, compute_layer_thermal
from .standards import (
    DEFAULT_TOLERANCE,
    REFERENCE_U_VALUES,
    get_reference_u_value,
    validate_against_reference,
)

__all__ = [
    # boundary
    "RSI_DEFAULT",
    "RSE_EXTERIOR",
    "RSE_INTERIOR",
    "get_rsi",
    "get_rse",
    "get_boundary_resistances",
    # layer
    "LayerThermalResult",
    "compute_layer_thermal",
    # component
    "ComponentThermalResult",
    "compute_component_thermal",
    # element
    "ElementThermalResult",
    "compute_element_thermal",
    # standards
    "REFERENCE_U_VALUES",
    "DEFAULT_TOLERANCE",
    "get_reference_u_value",
    "validate_against_reference",
]
