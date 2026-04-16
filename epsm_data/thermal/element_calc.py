"""Element thermal calculations placeholder.

Expected contents:
- Apply interior/exterior boundary resistances by element application.
- Compute final element U-value and diagnostics.
"""

from epsm_data.domain.enums import BuildingElement
from epsm_data.domain.element import Elements

from epsm_data.thermal.boundary_conditions import RSI, get_rse

def compute_r_total(element: "Elements") -> float:
    """Compute total thermal resistance including surface resistances [m2·K/W].

    R_total = RSI + sum(component R-values) + RSE

    RSI and RSE are sourced from thermal/boundary_conditions.py per ISO 6946.

    Args:
        element: Elements instance to compute resistance for.

    Returns:
        Total thermal resistance in m2·K/W.
    """
    rse = get_rse(element.application)
    return RSI + sum(c.r_sum for c in element.components) + rse

def compute_u_value(element: "Elements") -> float:
    """Compute thermal transmittance [W/m2·K].

    U = 1 / R_total

    Args:
        element: Elements instance to compute transmittance for.

    Returns:
        Thermal transmittance in W/m2·K.

    Raises:
        ValueError: If R_total is zero or negative.
    """
    r = compute_r_total(element)
    if r <= 0:
        raise ValueError(f"Element '{element.name}': R-value <= 0.")
    return 1 / r