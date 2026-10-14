"""Compatibility entry point; building application is owned by epsm."""


def resolve_building_archetype(*args, **kwargs):
    """Forward an explicit legacy request to EPSM's building adapter."""
    from epsm.catalogue_application import resolve_building_archetype as resolve
    return resolve(*args, **kwargs)
