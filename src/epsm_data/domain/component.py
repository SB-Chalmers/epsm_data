"""Component domain entity.

A Component is an ordered assembly of layers within a shearing layer,
assigned to a building element role (roof, wall, floor, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from .editing import Editable
from .enums import BuildingElement, ShearingLayer
from .layer import Layer


@dataclass(frozen=True)
class LayerSlot(Editable):
    """Position a layer within a component stack.

    Parameters
    ----------
    layer : Layer
        Resolved layer composition.
    position : int
        Outside-to-inside ordering index.
    """

    layer: Layer
    position: int

    def __post_init__(self):
        if not isinstance(self.layer, Layer):
            raise ValueError("LayerSlot requires a Layer")
        if isinstance(self.position, bool) or not isinstance(self.position, int) or self.position < 0:
            raise ValueError("Layer position must be a nonnegative integer")


@dataclass(frozen=True)
class Component(Editable):
    """An ordered stack belonging to one shearing layer.

    Parameters
    ----------
    name, archetype : str
        Component identity and owning archetype label.
    application : BuildingElement
        Element role.
    layers : tuple of LayerSlot
        Non-empty outside-to-inside layer stack.
    shearing_layer : ShearingLayer
        Component grouping, such as Skin or Structure.
    """

    name: str
    archetype: str
    application: BuildingElement
    layers: Tuple[LayerSlot, ...]
    shearing_layer: ShearingLayer

    def __post_init__(self) -> None:
        object.__setattr__(self, "layers", tuple(self.layers))
        if any(not isinstance(slot, LayerSlot) for slot in self.layers):
            raise ValueError("layers must contain LayerSlot records")
        positions = [slot.position for slot in self.layers]
        if len(set(positions)) != len(positions):
            raise ValueError("Layer positions must be unique")
        object.__setattr__(self, "layers", tuple(sorted(self.layers, key=lambda s: s.position)))
        object.__setattr__(self, "application", BuildingElement(self.application))
        object.__setattr__(self, "shearing_layer", ShearingLayer(self.shearing_layer))
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
        """Return a component summary with ordered layer references.

        Returns
        -------
        dict
            JSON-compatible values. Referenced objects remain named links;
            use archetype_to_dict for the complete resolved hierarchy.
        """
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
