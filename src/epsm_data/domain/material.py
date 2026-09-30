"""Material domain entities.

Frozen dataclasses for opaque and window materials with physical
property validation.  No I/O or framework dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from .enums import Roughness


@dataclass(frozen=True)
class EmbodiedCarbon:
    """Resolved embodied-carbon properties using the legacy Boverket field names.

    Parameters
    ----------
    name, resource_id, boverket_name : str
        Display label, source identity, and original source label.
    A1_A3_conservative, A1_A3_typical : float
        Production impacts in kg CO2e/kg.
    A4_transport, A5_conservative : float
        Transport and installation impacts in kg CO2e/kg.
    conservative_factor : float
        Non-negative conversion multiplier.
    conversion_factor : float or None
        Volumetric conversion in kg/m³; None means not supplied by the source.
    technical_service_life : str
        Source description, retained verbatim; no aging model is attached.
    biogenic_carbon : float or None
        Biogenic carbon in kg CO2e/kg, including signed values; None if absent.

    Notes
    -----
    This type holds resolved values. It never fetches or verifies source data.
    """

    name: str
    resource_id: str
    boverket_name: str
    A1_A3_conservative: float  # kg CO2e/kg
    A1_A3_typical: float  # kg CO2e/kg
    A4_transport: float  # kg CO2e/kg
    A5_conservative: float  # kg CO2e/kg
    conservative_factor: float  # multiplier (e.g. 1.25)
    conversion_factor: float | None  # kg/m3; unknown is not 1
    technical_service_life: str  # may contain symbols like '<', '>'
    biogenic_carbon: float | None  # kg CO2e/kg; unknown is not zero

    def __post_init__(self) -> None:
        floats = [
            self.A1_A3_conservative,
            self.A1_A3_typical,
            self.A4_transport,
            self.A5_conservative,
            self.conservative_factor,
        ]
        if self.conversion_factor is not None:
            floats.append(self.conversion_factor)
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in floats):
            raise ValueError(f"Embodied carbon values must be non-negative for '{self.name}'.")
        if self.A1_A3_conservative < self.A1_A3_typical:
            raise ValueError("A1-A3 conservative value cannot be lower than typical value.")
        if self.biogenic_carbon is not None and (
            isinstance(self.biogenic_carbon, bool)
            or not isinstance(self.biogenic_carbon, (int, float))
            or not math.isfinite(self.biogenic_carbon)
        ):
            raise ValueError("Biogenic carbon must be finite or unknown.")

    def to_dict(self) -> dict:
        """Return resolved material properties and source identifiers.

        Returns
        -------
        dict
            JSON-compatible values. Referenced objects remain named links;
            use archetype_to_dict for the complete resolved hierarchy.
        """
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
    """Resolved physical properties of an opaque material.

    Parameters
    ----------
    name, json_id, boverket_id, material_type : str
        Identity, legacy source references, and material classification.
    roughness : Roughness
        EnergyPlus surface roughness category.
    density : float
        Density in kg/m³.
    specific_heat : float
        Specific heat capacity in J/(kg K).
    thermal_absorptance, solar_absorptance, visible_absorptance : float
        Dimensionless absorption fractions.
    conductivity : float
        Thermal conductivity in W/(m K), within 0.01 to 400.
    embodied_carbon : EmbodiedCarbon or None
        Resolved carbon record, or None when mapping is pending. Unknown is not zero.
    uuid : UUID, optional
        Material instance identity; generated if omitted.

    Examples
    --------
    See examples/archetype.py for explicit construction with synthetic values.
    """

    name: str
    json_id: str
    boverket_id: str | None
    material_type: str
    roughness: Roughness
    density: float
    specific_heat: float
    thermal_absorptance: float
    solar_absorptance: float
    visible_absorptance: float
    conductivity: float
    embodied_carbon: EmbodiedCarbon | None
    uuid: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Material name cannot be empty.")
        if self.conductivity is None or self.conductivity <= 0:
            raise ValueError("Conductivity must be positive.")
        if not (0.01 <= self.conductivity <= 400):
            raise ValueError("Conductivity outside realistic range (0.01-400 W/mK).")

    def to_dict(self) -> dict:
        """Return resolved material properties and source identifiers.

        Returns
        -------
        dict
            JSON-compatible values. Referenced objects remain named links;
            use archetype_to_dict for the complete resolved hierarchy.
        """
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
            "embodied_carbon": self.embodied_carbon.to_dict() if self.embodied_carbon else None,
        }


@dataclass(frozen=True)
class WindowMaterial:
    """Resolved material-level glazing properties.

    Parameters
    ----------
    name, json_id, boverket_id, material_type : str
        Display label, legacy source references, and classification.
    conductivity : float
        Conductivity in W/(m K).
    solar_transmittance, solar_reflectance_front, solar_reflectance_back : float
        Dimensionless solar properties.
    emissivity, dirt_correction : float
        Dimensionless longwave and dirt correction properties.
    solar_diffusing : bool
        Whether transmitted solar radiation is diffuse.
    embodied_carbon : EmbodiedCarbon or None
        Resolved carbon record, or None when mapping is pending.
    uuid : UUID, optional
        Material instance identity; generated if omitted.

    Notes
    -----
    The current builder uses whole-window WindowElement properties. This
    material type is retained for callers holding explicit glazing data.
    """

    name: str
    json_id: str
    boverket_id: str | None
    material_type: str
    conductivity: float
    solar_transmittance: float
    solar_reflectance_front: float
    solar_reflectance_back: float
    emissivity: float
    dirt_correction: float
    solar_diffusing: bool
    embodied_carbon: EmbodiedCarbon | None
    uuid: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Material name cannot be empty.")
        if self.conductivity is None or self.conductivity <= 0:
            raise ValueError("Conductivity must be positive.")
        if not (0.01 <= self.conductivity <= 400):
            raise ValueError("Conductivity outside realistic range (0.01-400 W/mK).")

    def to_dict(self) -> dict:
        """Return resolved material properties and source identifiers.

        Returns
        -------
        dict
            JSON-compatible values. Referenced objects remain named links;
            use archetype_to_dict for the complete resolved hierarchy.
        """
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
            "embodied_carbon": self.embodied_carbon.to_dict() if self.embodied_carbon else None,
        }
