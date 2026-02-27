from dataclasses import dataclass, field
from uuid import UUID, uuid4
from typing import Tuple
from enum import Enum

# Roughness enum for material surface texture
class Roughness(Enum):
    SMOOTH = "Smooth"
    MEDIUM_SMOOTH = "MediumSmooth"
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

class BuildingElementType(Enum):
    EXTERNALWALL = "ExternalWall"
    EXTERIORWALL = "ExteriorWall"
    INTERIORWALLBEARING = "InteriorWallBearing"
    INTERIORWALLNONBEARING = "InteriorWallNonBearing"
    BOTTOMFLOOR = "BottomFloor"
    INTERMEDIATEFLOOR = "IntermediateFloor"
    TOPFLOOR = "TopFloor"
    ROOF = "Roof"

    @classmethod
    def from_name(cls, name: str) -> "BuildingElementType | None":
        """
        Case-insensitive search for a known element type substring within name.
        Tries longer matches first to avoid WALL matching EXTERNALWALL early.
        """
        name_upper = name.upper()
        # Sort by length descending so more specific matches win
        for member in sorted(cls, key=lambda m: len(m.name), reverse=True):
            if member.name.upper() in name_upper:
                return member
        return None

# Tabula reference U-values, make this into class maybe
TABULA_CMF = {
    "CMF_1940": {"roof": 0.36, "wall": 0.58, "window": 2.22, "floor": 0.32},
    "CMF_1950": {"roof": 0.36, "wall": 0.58, "window": 2.22, "floor": 0.32},
    "CMF_1960": {"roof": 0.20, "wall": 0.41, "window": 2.22, "floor": 0.26},
}

###########################################
@dataclass(frozen=True)
class EmbodiedCarbon:
    name: str
    resource_id: str
    boverket_name:str
    A1_A3_conservative: float   # kg CO₂e/kg
    A1_A3_typical: float        # kg CO₂e/kg
    A4_transport: float         # kg CO₂e/kg
    A5_conservative: float      # kg CO₂e/kg
    conservative_factor: float  # multiplier (e.g. 1.25)
    conversion_factor: float    # kg/m³
    technical_service_life: str # years, when calling the api it gives some extra symbols (<,>, etc)
    biogenic_carbon: float      # kg CO₂e/kg

    def __post_init__(self):
        floats = [
            self.A1_A3_conservative, self.A1_A3_typical,
            self.A4_transport, self.A5_conservative,
            self.conservative_factor, self.conversion_factor,
        ]
        if any(v < 0 for v in floats):
            raise ValueError(f"Embodied carbon values must be non-negative for '{self.name}'.")
        
        if self.A1_A3_conservative < self.A1_A3_typical:
            raise ValueError(
                "A1-A3 conservative value cannot be lower than typical value."
            )
        # if not (1 <= self.technical_service_life <= 200):
        #     raise ValueError(
        #         "Technical service life must be between 1 and 200 years."
        #     ) # need to convert from string :))))
        
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "resource_id": self.resource_id,
            "boverket_name": self.boverket_name,
            "A1_A3_conservative": self.A1_A3_conservative,
            "A1_A3_typical": self.A1_A3_typical,
            "A4_transport": self.A4_transport,
            "A5_conservative": self.A5_conservative,
            "conservative_factor": self.conservative_factor,
            "conversion_factor": self.conversion_factor,
            "technical_service_life": self.technical_service_life,
            "biogenic_carbon": self.biogenic_carbon,
        }
        
####################################
@dataclass(frozen=True)
class OpaqueMaterial:
    name: str
    json_id: str
    boverket_id: str
    material_type: str
    roughness: Roughness
    density: float
    specific_heat: float
    thermal_absorptance: float
    solar_absorptance: float
    visible_absorptance: float
    conductivity: float
    embodied_carbon: EmbodiedCarbon
    uuid: UUID = field(default_factory=uuid4)  # generates one UUID per instance

    def __post_init__(self):
        if self.embodied_carbon is None:
            raise ValueError("Embodied carbon data missing.")
        
        if not self.name:
            raise ValueError("Material name cannot be empty.")

        if self.conductivity is None or self.conductivity <= 0:
            raise ValueError("Conductivity must be positive.")
        elif not (0.01 <= self.conductivity <= 400):
            raise ValueError("Conductivity outside realistic range (0.01–400 W/mK).")
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "uuid": str(self.uuid),
            "json_id": self.json_id,
            "boverket_id": self.boverket_id,
            "material_type": self.material_type,
            "roughness": self.roughness.value, # string
            "density": self.density,
            "specific_heat": self.specific_heat,
            "thermal_absorptance": self.thermal_absorptance,
            "solar_absorptance": self.solar_absorptance,
            "visible_absorptance": self.visible_absorptance,
            "conductivity": self.conductivity,
            "embodied_carbon": self.embodied_carbon.to_dict(),
        }

@dataclass(frozen=True)
class WindowMaterial: #Need to implement this class 
    name: str
    json_id: str
    boverket_id: str
    material_type: str
    conductivity: float
    solar_transmittance: float
    solar_reflectance_front: float
    solar_reflectance_back: float
    emissivity: float
    dirt_correction: float
    solar_diffusing: bool
    embodied_carbon: EmbodiedCarbon
    uuid: UUID = field(default_factory=uuid4)  # generates one UUID per instance

    def __post_init__(self):
        if self.embodied_carbon is None:
            raise ValueError("Embodied carbon data missing.")
        
        if not self.name:
            raise ValueError("Material name cannot be empty.")

        if self.conductivity is None or self.conductivity <= 0:
            raise ValueError("Conductivity must be positive.")
        elif not (0.01 <= self.conductivity <= 400):
            raise ValueError("Conductivity outside realistic range (0.01–400 W/mK).")
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "uuid": str(self.uuid),
            "json_id": self.json_id,
            "boverket_id": self.boverket_id,
            "material_type": self.material_type,
            "conductivity": self.conductivity,
            "solar_transmittance": self.solar_transmittance,
            "solar_reflectance_front": self.solar_reflectance_front,
            "solar_reflectance_back": self.solar_reflectance_back,
            "emissivity": self.emissivity,
            "dirt_correction": self.dirt_correction,
            "solar_diffusing": self.solar_diffusing,
            "embodied_carbon": self.embodied_carbon.to_dict(),
        }
        
          
####################################
@dataclass(frozen=True)
class Layer:
    name: str
    layer_code: str
    thickness: float
    materials: Tuple[Tuple[OpaqueMaterial, float, float], ...]  # (material, area_fraction, thickness)
    archetype: str
    is_composite: bool = False

    def __post_init__(self):
        if self.thickness <= 0:
            raise ValueError(f"Layer '{self.name}': thickness must be greater than zero.")

        if not self.materials:
            raise ValueError(f"Layer '{self.name}': must have at least one material.")

        total_frac = sum(frac for _, frac, _ in self.materials)
        if not (0.999 <= total_frac <= 1.001):
            raise ValueError(
                f"Layer '{self.name}': area fractions sum to {total_frac:.4f}, expected 1.0."
            )

        if self.is_composite and len(self.materials) < 2:
            raise ValueError(
                f"Layer '{self.name}': marked composite but only has {len(self.materials)} material."
            )
        if not self.is_composite and len(self.materials) > 1:
            raise ValueError(
                f"Layer '{self.name}': has {len(self.materials)} materials but not marked as composite."
            )

    def check_thickness_consistency(self) -> str | None:
        """
        Soft thickness check — returns a warning string if inconsistent, None if OK.
        Kept separate from __post_init__ so the loader can treat it as a warning
        and still keep the instance rather than discarding it.
        """
        mat_thicknesses = [t for _, _, t in self.materials]

        if not self.is_composite:
            mat_t = mat_thicknesses[0]
            if abs(mat_t - self.thickness) > 0.0001:
                return (
                    f"Single material thickness {mat_t:.4f} m "
                    f"does not match layer thickness {self.thickness:.4f} m"
                )
        else:
            total = sum(mat_thicknesses)
            if abs(total - self.thickness) > 0.0001:
                return (
                    f"Material thicknesses sum to {total:.4f} m "
                    f"but layer thickness is {self.thickness:.4f} m"
                )
        return None

    @property
    def r_value(self) -> float:
        """
        Effective R-value [m²·K/W].
        Single material: U-value method R = d / lambda.
        Composite: weighted average of lambda method and U-value method.
        """
        d = self.thickness

        if len(self.materials) == 1:
            mat, _, _ = self.materials[0]
            if mat.conductivity <= 0:
                return 0.0
            return d / mat.conductivity

        avg_lambda = sum(mat.conductivity * frac for mat, frac, _ in self.materials)
        if avg_lambda <= 0:
            raise ValueError(
                f"Invalid average conductivity ({avg_lambda}) in layer {self.name}"
            )

        r_lambda_method = d / avg_lambda
        total_u = sum((mat.conductivity / d) * frac for mat, frac, _ in self.materials)
        r_u_method = 1 / total_u if total_u > 0 else 0.0

        return 0.5 * (r_lambda_method + r_u_method)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "layer_code": self.layer_code,
            "thickness": self.thickness,
            "archetype": self.archetype,
            "is_composite": self.is_composite,
            "r_value": round(self.r_value, 6),
            "materials": [
                {
                    "material_name": mat.name,  # reference by name, not nested
                    "area_fraction": frac,
                    "thickness": t,
                }
                for mat, frac, t in self.materials
            ],
        }
          
####################################
@dataclass(frozen=True)
class Components:
    name: str
    archetype: str
    layers: Tuple[Tuple[Layer, int], ...]
    shearing_layer: ShearingLayer

    def __post_init__(self):
        if not self.layers:
            raise ValueError("Component is missing layers.")

    @property
    def r_sum(self) -> float:
        """Sum of all layer R-values — no rsi/rse, those are applied at Element level."""
        return sum(layer.r_value for layer, _ in self.layers)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "archetype": self.archetype,
            "shearing_layer": self.shearing_layer.value,  # Enum → string ?
            "r_sum": round(self.r_sum, 6),
            "thickness": self.thickness,
            "layers": [
                {"layer_code": layer.layer_code, "layer_index": idx}
                for layer, idx in self.layers
            ],
        }
    
    @property
    def thickness(self) -> float:
        """Total thickness of all layers."""
        return sum(layer.thickness for layer, _ in self.layers)
         
####################################
@dataclass(frozen=True)
class Elements:
    name: str
    archetype: str
    age: int
    components: Tuple[Components, ...]
    element_type: BuildingElementType  # new field

    def __post_init__(self):
        if not self.components:
            raise ValueError(f"Element '{self.name}': missing components.")

    @property
    def u_value(self) -> float:
        rsi = 0.13
        rse = 0.04
        r_total = rsi + sum(component.r_sum for component in self.components) + rse
        if r_total <= 0:
            raise ValueError(f"Element '{self.name}': R-value <= 0.")
        return 1 / r_total

    def check_tabula(self, tabula_data: dict) -> str | None:
        type_to_tabula = {
            BuildingElementType.EXTERNALWALL:           "wall",
            BuildingElementType.EXTERIORWALL:           "wall",
            BuildingElementType.INTERIORWALLBEARING:    "wall",
            BuildingElementType.INTERIORWALLNONBEARING: "wall",
            BuildingElementType.BOTTOMFLOOR:            "floor",
            BuildingElementType.INTERMEDIATEFLOOR:      "floor",
            BuildingElementType.TOPFLOOR:               "roof",
            BuildingElementType.ROOF:                   "roof",
        } #Best way?

        name_upper = self.name.upper()
        matched_archetype = next(
            (k for k in tabula_data if k.upper() in name_upper), None
        )
        if matched_archetype is None:
            return "Archetype not found in Tabula data"

        matched_type = type_to_tabula.get(self.element_type)
        if matched_type is None:
            return f"No Tabula mapping for element type '{self.element_type.value}'"

        tabula_u = tabula_data[matched_archetype][matched_type]
        if self.u_value > tabula_u:
            return (
                f"U-value {self.u_value:.4f} exceeds Tabula threshold "
                f"{tabula_u} for {matched_archetype} {matched_type}"
            )
        return None
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "archetype": self.archetype,
            "age": self.age,
            "element_type": self.element_type.value, 
            "u_value": round(self.u_value, 6),
            "r_total": round(0.13 + sum(c.r_sum for c in self.components) + 0.04, 6),
            "components": [comp.name for comp in self.components],
        }
    
####################################
@dataclass(frozen=True)
class Buildings:
    name: str
    age: int
    elements: Tuple[Tuple[str, BuildingElementType], ...]  # (element_name, element_type)

    def __post_init__(self):
        if not self.elements:
            raise ValueError(f"Building '{self.name}': has no elements.")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "age": self.age,
            "elements": [
                {"element_name": el_name, "element_type": el_type.value}
                for el_name, el_type in self.elements
            ],
        }
        