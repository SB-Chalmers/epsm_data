from typing import List
from EPSM_Enums import ShearingLayer
from Layers import Layer, Concrete_Layer, Franken_Layer  # Same thing here
from datetime import datetime


# needs RSC (how to calcultae??) look up somehow - default value if nothing exists. 
#Fine to leave as a null (but with a note)
# shearing layer (or the layer with the brandt assigning)

# test folder with pytest four tests composite values
# U values are corrects /error validation is checkl 
# every class that a test.
# Connection between RSE and shearing layers. 


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
        year_installed: int = None,
        rsi: float = 0.13,  # internal surface resistance [m²·K/W]
        rse: float = 0.04,  # external surface resistance [m²·K/W]
        
    ):
        self.name = name
        self.layers = layers
        self.rsi = rsi
        self.rse = rse
        self.shearing_layer = shearing_layer
        self.r_value_total = self.calculate_r_value()
        self.year_installed = year_installed


    def calculate_r_value(self) -> float:
        """Total R-value including surface resistances."""
        layer_r_total = sum(layer.r_value for layer in self.layers if layer.r_value)
        return self.rsi + layer_r_total + self.rse
    
    @property
    def age(self) -> int:
        """Calculate the age of the component."""
        current_year = datetime.now().year
        return current_year - self.year_installed

    
    def print_info(self):
        print(f"Component: {self.name} ")
        print(f"Shearing Layer: {self.shearing_layer.value} ")
        for i, layer in enumerate(self.layers, start=1):
            print(f"  Layer {i}: {layer.r_value} m²·K/W")
        print(f"  Total R: {self.r_value_total} m²·K/W")
        print(f"Age: {self.age} years")

    def to_dict(self):
        """Serialize for export."""
        return {
            "name": self.name,
            "rsi": self.rsi,
            "rse": self.rse,
            "shearing_layer": self.shearing_layer.value,
            "r_value_total": self.r_value_total,
            "layers": [layer.to_dict() for layer in self.layers],
            "age": self.age
        }

###### Example

wall_component = Component(
    name="Concrete + Insulation Wall",
    layers=[Concrete_Layer(), Franken_Layer()],
    shearing_layer=ShearingLayer.EXTERIOR,  
    year_installed=2020
)


wall_component.print_info()