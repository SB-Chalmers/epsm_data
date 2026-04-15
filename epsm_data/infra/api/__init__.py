"""External API adapters."""

from .boverket_client import (
    build_resource_lookup,
    fetch_all_materials,
    parse_embodied_carbon,
)

__all__ = [
    "build_resource_lookup",
    "fetch_all_materials",
    "parse_embodied_carbon",
]
