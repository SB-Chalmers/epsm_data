"""Boundary condition constants for thermal calculations.

Surface resistances per SS-EN ISO 6946 (building components).
RSI = interior surface resistance, RSE = exterior surface resistance.
"""

from __future__ import annotations

from epsm_data.domain.enums import BuildingElement

# Standard surface resistances [m²·K/W] per ISO 6946
RSI_DEFAULT = 0.13  # interior surface, horizontal heat flow
RSE_EXTERIOR = 0.04  # exterior surface
RSE_INTERIOR = 0.13  # interior-to-interior (symmetric)

# Elements treated as interior (symmetric boundary)
_INTERIOR_ELEMENTS = frozenset({
    BuildingElement.INT_WALL_LOADBEARING,
    BuildingElement.INT_WALL_NONLOADBEARING,
    BuildingElement.INTERMEDIATE_FLOOR,
})


def get_rsi(application: BuildingElement) -> float:
    """Interior surface resistance [m²·K/W]."""
    return RSI_DEFAULT


def get_rse(application: BuildingElement) -> float:
    """Exterior surface resistance [m²·K/W].

    Interior elements (partitions, intermediate floors) use symmetric
    boundary conditions (RSE = RSI).
    """
    if application in _INTERIOR_ELEMENTS:
        return RSE_INTERIOR
    return RSE_EXTERIOR


def get_boundary_resistances(application: BuildingElement) -> tuple[float, float]:
    """Return (RSI, RSE) for the given building element application."""
    return get_rsi(application), get_rse(application)
