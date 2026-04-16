"""Component entity placeholder.

Expected responsibilities:
- Ordered layer assembly.
- Envelope/internal wall classification.
- Shearing layer assignment and component-level metadata.
"""

from epsm_data.domain.enums import ShearingLayer, BuildingElement
from epsm_data.domain.layer import Layer
from dataclasses import dataclass
from typing import Tuple

@dataclass(frozen=True)
class Components:
    name: str
    archetype: str
    application: BuildingElement
    layers: Tuple[Tuple[Layer, int], ...]
    shearing_layer: ShearingLayer

    def __post_init__(self):
        if not self.layers:
            raise ValueError("Component is missing layers.")

    @property
    def r_sum(self) -> float:
        from epsm_data.thermal.component_calc import compute_r_sum
        return compute_r_sum(self)
    
    @property
    def thickness(self) -> float:
        """Total thickness of all layers."""
        return sum(layer.thickness for layer, _ in self.layers)
    
    @property
    def is_long_lived(self) -> bool:
        """True if all layers in the component are long-lived."""
        return all(layer.is_long_lived for layer, _ in self.layers)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "archetype": self.archetype,
            "application": self.application.value,
            "shearing_layer": self.shearing_layer.value,
            "r_sum": round(self.r_sum, 6),
            "thickness": self.thickness,
            "is_long_lived": self.is_long_lived,
            "layers": [
                {"layer_code": layer.layer_code, "layer_index": idx}
                for layer, idx in self.layers
            ],
        }