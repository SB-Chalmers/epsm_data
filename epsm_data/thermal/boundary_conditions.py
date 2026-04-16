"""Boundary conditions.

Standardized surface resistance values per ISO 6946.
RSI = interior surface resistance [m2·K/W]
RSE = exterior surface resistance [m2·K/W]

- Climate/usage-specific overrides.
"""

from epsm_data.domain.enums import BuildingElement

# Interior surface resistance — same for all elements
RSI = 0.13

# Exterior surface resistance — differs for internal vs external elements
RSE_EXTERNAL = 0.04  # external envelope (walls, roof, ground floor)
RSE_INTERNAL = 0.13  # internal partitions and intermediate floors

# Elements that use RSE_INTERNAL instead of RSE_EXTERNAL
INTERNAL_ELEMENTS = (
    BuildingElement.INT_WALL_LOADBEARING,
    BuildingElement.INT_WALL_NONLOADBEARING,
    BuildingElement.INTERMEDIATE_FLOOR,
)

def get_rse(application: BuildingElement) -> float:
    """Return the exterior surface resistance for a given building element."""
    return RSE_INTERNAL if application in INTERNAL_ELEMENTS else RSE_EXTERNAL
