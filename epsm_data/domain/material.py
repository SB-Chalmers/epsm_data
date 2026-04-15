"""Material domain entities.

Frozen dataclasses for opaque and window materials with physical
property validation.  No I/O or framework dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from .enums import Roughness


@dataclass(frozen=True)
class EmbodiedCarbon:
    """Embodied-carbon data sourced from the Boverket climate database."""

    name: str
    resource_id: str
    boverket_name: str
    A1_A3_conservative: float  # kg CO2e/kg
    A1_A3_typical: float  # kg CO2e/kg
    A4_transport: float  # kg CO2e/kg
    A5_conservative: float  # kg CO2e/kg
    conservative_factor: float  # multiplier (e.g. 1.25)
    conversion_factor: float  # kg/m3
    technical_service_life: str  # may contain symbols like '<', '>'
    biogenic_carbon: float  # kg CO2e/kg

    def __post_init__(self) -> None:
        floats = [
            self.A1_A3_conservative,
            self.A1_A3_typical,
            self.A4_transport,
            self.A5_conservative,
            self.conservative_factor,
            self.conversion_factor,
        ]
        if any(v < 0 for v in floats):
            raise ValueError(
                f"Embodied carbon values must be non-negative for '{self.name}'."
            )
        if self.A1_A3_conservative < self.A1_A3_typical:
            raise ValueError(
                "A1-A3 conservative value cannot be lower than typical value."
            )

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


@dataclass(frozen=True)
class OpaqueMaterial:
    """Physical properties of an opaque envelope material."""

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
    uuid: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.embodied_carbon is None:
            raise ValueError("Embodied carbon data missing.")
        if not self.name:
            raise ValueError("Material name cannot be empty.")
        if self.conductivity is None or self.conductivity <= 0:
            raise ValueError("Conductivity must be positive.")
        if not (0.01 <= self.conductivity <= 400):
            raise ValueError("Conductivity outside realistic range (0.01-400 W/mK).")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "uuid": str(self.uuid),
            "json_id": self.json_id,
            "boverket_id": self.boverket_id,
            "material_type": self.material_type,
            "roughness": self.roughness.value,
            "density": self.density,
            "specific_heat": self.specific_heat,
            "thermal_absorptance": self.thermal_absorptance,
            "solar_absorptance": self.solar_absorptance,
            "visible_absorptance": self.visible_absorptance,
            "conductivity": self.conductivity,
            "embodied_carbon": self.embodied_carbon.to_dict(),
        }


@dataclass(frozen=True)
class WindowMaterial:
    """Physical properties of a window glazing material."""

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
    uuid: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.embodied_carbon is None:
            raise ValueError("Embodied carbon data missing.")
        if not self.name:
            raise ValueError("Material name cannot be empty.")
        if self.conductivity is None or self.conductivity <= 0:
            raise ValueError("Conductivity must be positive.")
        if not (0.01 <= self.conductivity <= 400):
            raise ValueError("Conductivity outside realistic range (0.01-400 W/mK).")

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
