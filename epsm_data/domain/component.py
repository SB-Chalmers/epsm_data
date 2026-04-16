"""Component domain entity.

A Component is an ordered assembly of layers within a shearing layer,
assigned to a building element role (roof, wall, floor, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from .enums import BuildingElement, ShearingLayer
from .layer import Layer


@dataclass(frozen=True)
class LayerSlot:
    """One layer positioned within a component stack."""

    layer: Layer
    position: int


@dataclass(frozen=True)
class Component:
    """An ordered stack of layers belonging to one shearing layer."""

    name: str
    archetype: str
    application: BuildingElement
    layers: Tuple[LayerSlot, ...]
    shearing_layer: ShearingLayer

    def __post_init__(self) -> None:
        if not self.layers:
            raise ValueError(f"Component '{self.name}': missing layers.")

    @property
    def r_sum(self) -> float:
        """Sum of all layer R-values (no boundary resistances)."""
        return sum(slot.layer.r_value for slot in self.layers)

    @property
    def thickness(self) -> float:
        """Total thickness of all layers [m]."""
        return sum(slot.layer.thickness for slot in self.layers)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "archetype": self.archetype,
            "application": self.application.value,
            "shearing_layer": self.shearing_layer.value,
            "r_sum": round(self.r_sum, 6),
            "thickness": self.thickness,
            "layers": [
                {"layer_code": slot.layer.layer_code, "layer_index": slot.position}
                for slot in self.layers
            ],
        }
