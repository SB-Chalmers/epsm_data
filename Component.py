from typing import List, Optional
from EPSM_Enums import ShearingLayer
from Layers import Layer, Concrete_Layer, Franken_Layer  # Same thing here

# needs RSC (how to calcultae??)
# shearing layer (or the layer with the brandt assigning)


class Component:
    """
    Represents a construction component (e.g., wall assembly)
    consisting of multiple layers and surface resistances.
    """

    def __init__(
        self,
        name: str,
        layers: List[Layer],
        shearing_layer: ShearingLayer,
        UUID: str,
        rsi: float = 0.13,  # internal surface resistance [m²·K/W]
        rse: float = 0.04,  # external surface resistance [m²·K/W]
        
        # shearing_layer: Optional[str] = None,
        # UUID: Optional[str] = None
    ):
        self.name = name
        self.layers = layers
        self.rsi = rsi
        self.rse = rse
        self.shearing_layer = shearing_layer
        self.r_value_total = self.calculate_r_value()
        self.UUID = UUID


    def calculate_r_value(self) -> float:
        """Total R-value including surface resistances."""
        layer_r_total = sum(layer.r_value for layer in self.layers if layer.r_value)
        return round(self.rsi + layer_r_total + self.rse, 5)

    
    def print_info(self):
        print(f"Component: {self.name} ")
        print(f"Shearing Layer: {self.shearing_layer.value} ")
        for i, layer in enumerate(self.layers, start=1):
            print(f"  Layer {i}: {layer.r_value} m²·K/W")
        print(f"  Total R: {self.r_value_total} m²·K/W")

    def to_dict(self):
        """Serialize for export."""
        return {
            "UUID": self.UUID,
            "name": self.name,
            "rsi": self.rsi,
            "rse": self.rse,
            "shearing_layer": self.shearing_layer,
            "r_value_total": self.r_value_total,
            "layers": [layer.to_dict() for layer in self.layers],
        }

###### Example

wall_component = Component(
    name="Concrete + Insulation Wall",
    layers=[Concrete_Layer, Franken_Layer],
)

wall_component.print_info()