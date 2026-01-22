from typing import List
from ClassDefinitions.Components import Component, wall_component
from EPSM_Enums import ShearingLayer

class Element:
    """
    Represents a construction element (e.g., wall, floor, roof)
    consisting of multiple components.
    """

    def __init__(self, name: str, element_components: List[Component]):
        self.name = name
        self.components = element_components  # only Component objects
        self.U_value_total = self.calculate_U_value()

    def calculate_U_value(self) -> float:
        """
        Calculate the overall U-value of the element.
        U = 1 / (sum of R-values including surface resistances)
        """
        total_R = sum(comp.r_value_total for comp in self.components)
        return round(1 / total_R, 5) if total_R > 0 else 0

    def print_info(self):
        print(f"Element: {self.name}")
        for i, comp in enumerate(self.components, start=1):
            print(f"\nComponent {i}: {comp.name} (Shearing Layer: {comp.shearing_layer.value})")
            comp.print_info()
        print(f"\nOverall Element U-value: {self.U_value_total} W/m²·K")

    def to_dict(self):
        return {
            "name": self.name,
            "U_value_total": self.U_value_total,
            "components": [comp.to_dict() for comp in self.components]
        }

###Example

wall_element = Element(
    name="Wall Assembly",
    element_components=[wall_component, wall_component]  
)

wall_element.print_info()

#External wall, roof, floor, basement floor, window