"""Compatibility shim for consumers importing boundary resistances (epsm_core)."""

from epsm_data.domain.element import surface_resistances

RSI_DEFAULT = 0.13
RSE_EXTERIOR = 0.04
RSE_INTERIOR = 0.13


def get_boundary_resistances(application):
    """Return (Rsi, Rse) in m² K/W per EN ISO 6946 for an element role."""
    return surface_resistances(application)


def get_rsi(application):
    return surface_resistances(application)[0]


def get_rse(application):
    return surface_resistances(application)[1]
