from abc import ABC, abstractmethod
from typing import Optional
from EPSM_Enums import Roughness

# is id necessary here or only for the element level?
# Boverket reference ?
# Do we want some type of embodied carbon property here?
# Units, find one standardised and annotate or separate class/ properties for units within the class?
# Need to figure out the shared properties handling


# Currently all of the common properties are listed in this base class.
class Material(ABC):
    """Abstract base class for all material types (opaque and window).
    Contains all of the shared properties."""

    def __init__(
        self,
        name: str,
        mat_type: str,
        UUID: str,
        conductivity: float,
        embodied_carbon: Optional[float] = None,
    ):
        self.name = name
        self.mat_type = mat_type
        self.UUID = UUID
        self.conductivity = conductivity
        self.embodied_carbon = embodied_carbon

    @abstractmethod
    def print_info(self):
        """Print material information."""
        pass

    @abstractmethod
    def to_dict(self) -> dict:
        """Serialize material to dictionary."""
        pass


class OpaqueMaterial(Material):
    """Represents opaque materials like concrete, gypsum, etc."""

    def __init__(
        self,
        roughness: Roughness,
        density: float,
        specific_heat: float,
        thermal_absorptance: float,
        solar_absorptance: float,
        visible_absorptance: float,
        **kwargs,  # name, type, UUID, conductivity, embodied_carbon handled by base class
    ):
        super().__init__(**kwargs)
        self.roughness = roughness
        self.density = density
        self.specific_heat = specific_heat
        self.thermal_absorptance = thermal_absorptance
        self.solar_absorptance = solar_absorptance
        self.visible_absorptance = visible_absorptance

    def print_info(self):
        super_info = f"[Opaque] {self.name} ({self.mat_type})\nID: {self.UUID}"
        conductivity_info = f"\nConductivity: {self.conductivity}"
        embodied_carbon_info = f"\nConductivity: {self.embodied_carbon}" if self.embodied_carbon else ""
 
        ""
        print(
            f"{super_info}"
            f"{conductivity_info}\n"
            f"{embodied_carbon_info}\n"
            f"Roughness: {self.roughness.value}\n"
            f"Density: {self.density}\n"
            f"Specific Heat: {self.specific_heat}\n"
            f"Thermal Absorptance: {self.thermal_absorptance}\n"
            f"Solar Absorptance: {self.solar_absorptance}\n"
            f"Visible Absorptance: {self.visible_absorptance}"
        )

    def to_dict(self):
        data = {
            "UUID": self.UUID,
            "name": self.name,
            "type": self.mat_type,
            "conductivity": self.conductivity,
            "roughness": self.roughness.value,
            "density": self.density,
            "specific_heat": self.specific_heat,
            "thermal_absorptance": self.thermal_absorptance,
            "solar_absorptance": self.solar_absorptance,
            "visible_absorptance": self.visible_absorptance,
        }
        return data


class WindowMaterial(Material):
    """Represents transparent or translucent window materials."""

    def __init__(
        self,
        solar_transmittance: float,
        solar_reflectance: float,
        solar_reflectance_back: float,
        visible_transmittance: float,
        visible_reflectance: float,
        visible_reflectance_back: float,
        infrared_transmittance: float,
        emissivity: float,
        emissivity_back: float,
        dirt_correction: float,
        solar_diffusing: bool,
        **kwargs,  # name, type, UUID, conductivity, embodied_carbon handled by base class
    ):
        super().__init__(**kwargs)
        self.solar_transmittance = solar_transmittance
        self.solar_reflectance = solar_reflectance
        self.solar_reflectance_back = solar_reflectance_back
        self.visible_transmittance = visible_transmittance
        self.visible_reflectance = visible_reflectance
        self.visible_reflectance_back = visible_reflectance_back
        self.infrared_transmittance = infrared_transmittance
        self.emissivity = emissivity
        self.emissivity_back = emissivity_back
        self.dirt_correction = dirt_correction
        self.solar_diffusing = solar_diffusing

    def print_info(self):
        super_info = f"[Window] {self.name} ({self.mat_type})\nID: {self.UUID}"
        conductivity_info = f"\nConductivity: {self.conductivity}"
        embodied_carbon_info = f"\nConductivity: {self.embodied_carbon}" if self.embodied_carbon else ""
 
        ""        
        print(
            f"{super_info}\n"
            f"{conductivity_info}\n"
            f"{embodied_carbon_info}\n"
            f"Solar Transmittance: {self.solar_transmittance}\n"
            f"Solar Reflectance (Front): {self.solar_reflectance}\n"
            f"Solar Reflectance (Back): {self.solar_reflectance_back}\n"
            f"Visible Transmittance: {self.visible_transmittance}\n"
            f"Visible Reflectance (Front): {self.visible_reflectance}\n"
            f"Visible Reflectance (Back): {self.visible_reflectance_back}\n"
            f"Infrared Transmittance: {self.infrared_transmittance}\n"
            f"Emissivity (Front): {self.emissivity}\n"
            f"Emissivity (Back): {self.emissivity_back}\n"
            f"Dirt Correction: {self.dirt_correction}\n"
            f"Solar Diffusing: {self.solar_diffusing}"
        )

    def to_dict(self):
        data = {
            "UUID": self.UUID,
            "name": self.name,
            "type": self.mat_type,
            "conductivity": self.conductivity,
            "solar_transmittance": self.solar_transmittance,
            "solar_reflectance": self.solar_reflectance,
            "solar_reflectance_back": self.solar_reflectance_back,
            "visible_transmittance": self.visible_transmittance,
            "visible_reflectance": self.visible_reflectance,
            "visible_reflectance_back": self.visible_reflectance_back,
            "infrared_transmittance": self.infrared_transmittance,
            "emissivity": self.emissivity,
            "emissivity_back": self.emissivity_back,
            "dirt_correction": self.dirt_correction,
            "solar_diffusing": self.solar_diffusing,
        }
        return data


######### Example usage ######################

# Opaque material
concrete = OpaqueMaterial(
    name="Concrete",
    mat_type="EnergyMaterial",
    UUID="mat-001",
    conductivity=1.8,
    roughness=Roughness.ROUGH,
    density=2300,
    specific_heat=880,
    thermal_absorptance=0.9,
    solar_absorptance=0.7,
    visible_absorptance=0.65,
    embodied_carbon=250
)


glass = WindowMaterial(
    name="Glass",
    mat_type="WindowMaterial",
    UUID="win-001",
    conductivity=1.2,
    solar_transmittance=0.8,
    solar_reflectance=0.1,
    solar_reflectance_back=0.12,
    visible_transmittance=0.9,
    visible_reflectance=0.08,
    visible_reflectance_back=0.1,
    infrared_transmittance=0.7,
    emissivity=0.84,
    emissivity_back=0.88,
    dirt_correction=1.0,
    solar_diffusing=False
)

# Print info
concrete.print_info()
glass.print_info()

# Export to dict
print(concrete.to_dict())
print(glass.to_dict())
