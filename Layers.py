from typing import List, Tuple, Optional, Union
from Materials import Material, concrete, glass #this needs to fixed for usability later on.

#How do we calculate R-value for composite layers? And U-value? for element was there a specific formula?
#Is the composite tactic uneccessary, better with two classes instead? and etc. 

class Layer:
    """
    Represents a construction layer — either homogeneous (one material)
    or composite (multiple materials sharing the same thickness).
    """

    def __init__(
        self,
        thickness: float, #m
        materials: Union[Material, List[Tuple[Material, float]]],
    ):
        """
        Parameters
        ----------
        thickness : float
            Layer thickness in meters.
            materials : Material or list of (Material, fraction)
            - Single Material → homogeneous layer.
            - List of (Material, area_fraction) → composite layer.
        """
        self.thickness = thickness

        # Normalize to a list of tuples
        if isinstance(materials, list):
            self.materials = materials
        else:
            self.materials = [(materials, 1.0)]

        # Calculate effective R-value
        self.r_value = self.calculate_r_value()

    def calculate_r_value(self) -> Optional[float]:
        """Compute equivalent thermal resistance (m²·K/W)."""
        u_total = 0.0
        for mat, fraction in self.materials:
            if not mat.conductivity or mat.conductivity <= 0:
                continue
            r_i = self.thickness / mat.conductivity
            u_i = 1 / r_i
            u_total += fraction * u_i
        if u_total > 0:
            return round(1 / u_total, 5)
        return None

    def to_dict(self):
        """Return this layer as a dictionary for export or serialization."""
        return {
            "thickness": self.thickness,
            "r_value": self.r_value,
            "materials": [
                {
                    "name": mat.name,
                    "conductivity": mat.conductivity,
                    "fraction": fraction,
                }
                for mat, fraction in self.materials
            ],
        }
    
#############

# Example 1: Homogeneous layer (single material)
Concrete_Layer = Layer(
    thickness=0.2,
    materials=concrete  # existing OpaqueMaterial instance
)

# Example 2: Composite layer (multiple materials in parallell)
Franken_Layer = Layer(
    thickness=0.2,
    materials=[
        (concrete, 0.85),  # 85% concrete
        (glass, 0.15)         # 15% glass (fraction based on area)
    ]
)
