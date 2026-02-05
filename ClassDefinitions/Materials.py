import uuid
from abc import ABC, abstractmethod
from EPSM_Enums import Roughness
from ClassDefinitions.EmbodiedCarbon import EmbodiedCarbon


# ======================================================================
# Base Material
# ======================================================================
class Material(ABC):
    """
    Abstract base class for all material types.
    Materials are entities: they have identity and are reused.
    """

    def __init__(
        self,
        name: str,
        mat_type: str,
        conductivity: float,
        embodied_carbon: EmbodiedCarbon,
        json_id: str | None = None,
        boverket_id: str | None = None,
    ):
        # Canonical identity
        self.name = name.strip().lower()
        self.mat_type = mat_type or "EnergyMaterial"

        # Physical properties
        self.conductivity = conductivity
        self.embodied_carbon = embodied_carbon

        # Identifiers
        self.UUID = str(uuid.uuid4())
        self.json_id = json_id
        self.boverket_id = boverket_id

    # Validation
    def validate(self) -> list[str]:
        warnings = []
        if not self.name:
            warnings.append("Material name cannot be empty.")

        if self.conductivity is None or self.conductivity <= 0:
            warnings.append("Conductivity must be positive.")

        if self.embodied_carbon is None:
            warnings.append("Embodied carbon data missing.")

        return warnings


    # Derived / convenience
    @property
    def display_name(self) -> str:
        """Human-readable name."""
        return self.name.replace("_", " ").title()

    # Serialization helpers
    def base_dict(self) -> dict:
        return {
            "uuid": self.UUID,
            "name": self.name,
            "type": self.mat_type,
            "conductivity": self.conductivity,
        }

    def print_embodied_carbon(self) -> None:
        self.embodied_carbon.print_info()

    # Required interface
    @abstractmethod
    def print_info(self) -> None:
        pass

    @abstractmethod
    def to_dict(self) -> dict:
        pass


# ======================================================================
# Opaque Material
# ======================================================================
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
        **kwargs
    ):
        super().__init__(**kwargs)

        self.roughness = roughness
        self.density = density
        self.specific_heat = specific_heat
        self.thermal_absorptance = thermal_absorptance
        self.solar_absorptance = solar_absorptance
        self.visible_absorptance = visible_absorptance

    # Validation
    def validate(self) -> list[str]:
        """Check if values are reasonable, return list of warnings."""
        warnings = []

        if self.density <= 0:
            warnings.append("Density must be positive.")

        if self.specific_heat <= 0:
            warnings.append("Specific heat must be positive.")

        for prop_name, value in {
            "thermal_absorptance": self.thermal_absorptance,
            "solar_absorptance": self.solar_absorptance,
            "visible_absorptance": self.visible_absorptance,
        }.items():
            if not (0 <= value <= 0.5):
                warnings.append(f"{prop_name} must be between 0 and 0.5.")

        return warnings



    # Presentation
    def print_info(self) -> None:
        self.validate()

        print(f"[Opaque] {self.display_name} ({self.mat_type})")
        print(f"UUID: {self.UUID}")
        print(f"Conductivity: {self.conductivity}")
        print(f"Roughness: {self.roughness.value}")
        print(f"Density: {self.density}")
        print(f"Specific Heat: {self.specific_heat}")
        print(f"Thermal Absorptance: {self.thermal_absorptance}")
        print(f"Solar Absorptance: {self.solar_absorptance}")
        print(f"Visible Absorptance: {self.visible_absorptance}")
        self.print_embodied_carbon()

    # Serialization
    def to_dict(self) -> dict:
        self.validate()

        data = self.base_dict()
        data.update({
            "roughness": self.roughness.value,
            "density": self.density,
            "specific_heat": self.specific_heat,
            "thermal_absorptance": self.thermal_absorptance,
            "solar_absorptance": self.solar_absorptance,
            "visible_absorptance": self.visible_absorptance,
            "embodied_carbon": self.embodied_carbon.to_dict(),
        })
        return data


# ======================================================================
# Window Material
# ======================================================================
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
        **kwargs
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

    # Validation
    def validate(self) -> list[str]:
        warnings = super().validate()

        for prop_name, value in {
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
        }.items():
            if not (0 <= value <= 1):
                warnings.append(f"{prop_name} must be between 0 and 1.")

        return warnings


    # Presentation
    def print_info(self) -> None:
        self.validate()

        print(f"[Window] {self.display_name} ({self.mat_type})")
        print(f"UUID: {self.UUID}")
        print(f"Conductivity: {self.conductivity}")
        print(f"Solar Transmittance: {self.solar_transmittance}")
        print(f"Solar Reflectance (Front): {self.solar_reflectance}")
        print(f"Solar Reflectance (Back): {self.solar_reflectance_back}")
        print(f"Visible Transmittance: {self.visible_transmittance}")
        print(f"Visible Reflectance (Front): {self.visible_reflectance}")
        print(f"Visible Reflectance (Back): {self.visible_reflectance_back}")
        print(f"Infrared Transmittance: {self.infrared_transmittance}")
        print(f"Emissivity (Front): {self.emissivity}")
        print(f"Emissivity (Back): {self.emissivity_back}")
        print(f"Dirt Correction: {self.dirt_correction}")
        print(f"Solar Diffusing: {self.solar_diffusing}")
        self.print_embodied_carbon()

    # Serialization
    def to_dict(self) -> dict:
        self.validate()

        data = self.base_dict()
        data.update({
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
            "embodied_carbon": self.embodied_carbon.to_dict(),
        })
        return data
