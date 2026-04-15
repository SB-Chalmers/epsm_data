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
class Component:
    """An ordered stack of layers belonging to one shearing layer."""

    name: str
    archetype: str
    application: BuildingElement
    layers: Tuple[Tuple[Layer, int], ...]  # (layer, layer_index)
    shearing_layer: ShearingLayer

    def __post_init__(self) -> None:
        if not self.layers:
            raise ValueError(f"Component '{self.name}': missing layers.")

    @property
    def r_sum(self) -> float:
        """Sum of all layer R-values (no boundary resistances)."""
        return sum(layer.r_value for layer, _ in self.layers)

    @property
    def thickness(self) -> float:
        """Total thickness of all layers [m]."""
        return sum(layer.thickness for layer, _ in self.layers)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "archetype": self.archetype,
            "application": self.application.value,
            "shearing_layer": self.shearing_layer.value,
            "r_sum": round(self.r_sum, 6),
            "thickness": self.thickness,
            "layers": [
                {"layer_code": layer.layer_code, "layer_index": idx}
                for layer, idx in self.layers
            ],
        }
