"""Domain entities and value objects.

Immutable business objects — no pandas, SQLAlchemy, HTTP, or file-system
dependencies in this package.
"""

from .building import (
    BuildingArchetype,
    ConstructionSet,
    RenovationEvent,
    build_construction_set,
)
from .component import Component
from .element import Element, TABULA_CMF
from .enums import (
    BuildingElement,
    ComponentState,
    RenovationMeasureType,
    Roughness,
    ShearingLayer,
)
from .layer import Layer, LayerMaterial
from .material import EmbodiedCarbon, OpaqueMaterial, WindowMaterial

__all__ = [
    # enums
    "BuildingElement",
    "ComponentState",
    "RenovationMeasureType",
    "Roughness",
    "ShearingLayer",
    # material
    "EmbodiedCarbon",
    "OpaqueMaterial",
    "WindowMaterial",
    # layer
    "Layer",
    "LayerMaterial",
    # component
    "Component",
    # element
    "Element",
    "TABULA_CMF",
    # building
    "BuildingArchetype",
    "ConstructionSet",
    "RenovationEvent",
    "build_construction_set",
]
