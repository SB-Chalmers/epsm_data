"""The Swedish LoD2 archetype catalogue: selection, authoring, handover and exchange."""

from .authoring import build_archetype
from .catalogue import Catalogue
from .handover import export_nominal_constructions, validate_nominal_handover
from .keys import ArchetypeKey, ArchetypeSlot
from .reference import reference_construction_set, reference_hvac_template
from .serialization import (
    archetype_from_dict,
    archetype_to_dict,
    construction_set_from_dict,
    construction_set_to_dict,
)

__all__ = [
    "ArchetypeKey",
    "ArchetypeSlot",
    "Catalogue",
    "archetype_from_dict",
    "archetype_to_dict",
    "build_archetype",
    "construction_set_from_dict",
    "construction_set_to_dict",
    "export_nominal_constructions",
    "reference_construction_set",
    "reference_hvac_template",
    "validate_nominal_handover",
]
