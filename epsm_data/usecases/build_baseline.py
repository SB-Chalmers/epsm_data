"""Build baseline archetypes use-case.

Responsibilities:
- Load raw data (Excel, JSON, API) via infra adapters.
- Construct validated BuildingArchetype instances with baseline ConstructionSets.
- Compute and attach thermal properties via the thermal engine.
- Return archetype objects ready for scenario simulation or contract export.
"""


def run_build_baseline(*args, **kwargs):
    """Load, validate, and construct baseline BuildingArchetype instances."""
    raise NotImplementedError("Implement baseline build use-case")
