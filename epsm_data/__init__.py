"""epsm_data — Building archetype library for energy modelling.

This package defines building archetypes: material properties, thermal
performance, renovation measures, and aging behavior.  It is geometry-
and site-agnostic by design.

A downstream library (e.g. building_sim) consumes archetypes via the
consumption contract to instantiate geolocated buildings and run full
energy simulations.

Workflow:
    archetype = epsm_data.load_archetype("CMF_1950")
    contract  = archetype.to_consumption_contract()
    # hand contract to downstream geolocated-building library
"""

__all__ = [
    "domain",
    "thermal",
    "lifecycle",
    "usecases",
    "infra",
    "validation",
    "reporting",
    "config",
]
