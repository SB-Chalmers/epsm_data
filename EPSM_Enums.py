from enum import Enum
from dataclasses import dataclass

# Roughness enum for material surface texture
class Roughness(Enum):
    SMOOTH = "Smooth"
    MEDIUM_ROUGH = "MediumRough"
    ROUGH = "Rough"
    VERY_ROUGH = "VeryRough"

# Brands Shearing Layers 
class ShearingLayer(Enum):
    Skin = "Skin"
    Structure = "Structure"
    Services = "Services"
    Space = "Space"
    Stuff = "Stuff"

@dataclass
class EmbodiedCarbon:
    """
    Contains properties listed in Boverket's klimatdatabas 
    https://klimatdatabasen.boverket.se/
    """

    def __init__(
        self,
        product_name: str,
        resource_id: str,
        A1_A3_conservative: float, # kg CO₂e/kg
        A4: float, # kg CO₂e/kg
        A5_conservative: float, # kg CO₂e/kg
        A1_A3_typical: float , # kg CO₂e/kg
        A1_A3_factor_conservative: float, 
        A5_factor_byggspill: float,        
        conversion_factor: float, # kg/m³
        technical_service_life: int # years
    ):
        self.product_name = product_name
        self.resource_id = resource_id
        self.A1_A3_conservative = A1_A3_conservative
        self.A4 = A4
        self.A5_conservative = A5_conservative
        self.A1_A3_typical = A1_A3_typical
        self.A1_A3_factor_conservative = A1_A3_factor_conservative
        self.A5_factor_byggspill = A5_factor_byggspill
        self.conversion_factor = conversion_factor
        self.technical_service_life = technical_service_life

    def print_info(self):
        """Print all properties of the embodied carbon instance."""
        print("Embodied Carbon Information:")
        for key, value in self.to_dict().items():
            print(f"{key}: {value}")

    def to_dict(self):
        """Return a dictionary of all properties."""
        return {
            "product_name": self.product_name,
            "resource_id": self.resource_id,
            "A1_A3_conservative": self.A1_A3_conservative,
            "A4": self.A4,
            "A5_conservative": self.A5_conservative,
            "A1_A3_typical": self.A1_A3_typical,
            "A1_A3_factor_conservative": self.A1_A3_factor_conservative,
            "A5_factor_byggspill": self.A5_factor_byggspill,
            "conversion_factor": self.conversion_factor,
            "technical_service_life": self.technical_service_life,
            #Find definition of technical service life
        }

# Example usage https://klimatdatabasen.boverket.se/detaljer/1/6000000193

ec_cement = EmbodiedCarbon(
        product_name="Cement, typ CEM II/A-LL 42,5 R, Cement, type CEM II/A-LL 42,5 R",
        resource_id="6000000193",
        A1_A3_conservative=0.813,
        A4=0.0348,
        A5_conservative=0.0254,
        A1_A3_typical=0.65,
        A1_A3_factor_conservative=1.24,
        A5_factor_byggspill=1.03,
        conversion_factor=3040, 
        technical_service_life=50
    )

ec_cement.print_info()
print(ec_cement.to_dict())
