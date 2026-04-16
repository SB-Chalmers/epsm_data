"""Component thermal calculations placeholder.

Expected contents:
- Ordered layer aggregation to component-level R/U.
- Optional correction factors and bridge adjustments.
"""
from epsm_data.domain.component import Components

def compute_r_sum(component: Components) -> float:
    """Sum of all layer R-values. RSI/RSE are applied at element level."""
    return sum(layer.r_value for layer, _ in component.layers)

