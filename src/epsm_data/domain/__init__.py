"""Domain entities and value objects.

Immutable business objects — no pandas, SQLAlchemy, HTTP, or file-system
dependencies in this package.
"""

from .archetype import (
    Archetype,
    BuildingArchetype,
    ConstructionSet,
    RenovationEvent,
    build_construction_set,
)
from .component import Component, LayerSlot
from .element import Element, WindowElement
from .enums import (
    BuildingElement,
    ComponentState,
    RenovationMeasureType,
    Roughness,
    ShearingLayer,
)
from .envelope import EnvelopePerformance
from .layer import Layer, LayerMaterial
from .material import (
    CarbonReference,
    EmbodiedCarbon,
    EnvironmentalFactor,
    Material,
    OpaqueMaterial,
    WindowMaterial,
)

__all__ = [
    "EnvelopePerformance",
    "Archetype", "Material", "EnvironmentalFactor",
    # enums
    "BuildingElement",
    "ComponentState",
    "RenovationMeasureType",
    "Roughness",
    "ShearingLayer",
    # material
    "CarbonReference",
    "EmbodiedCarbon",
    "OpaqueMaterial",
    "WindowMaterial",
    # layer
    "Layer",
    "LayerMaterial",
    # component
    "Component",
    "LayerSlot",
    # element
    "Element",
    "WindowElement",
    # building
    "BuildingArchetype",
    "ConstructionSet",
    "RenovationEvent",
    "build_construction_set",
]
