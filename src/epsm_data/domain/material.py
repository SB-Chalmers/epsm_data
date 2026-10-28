"""Material domain entities.

Frozen dataclasses for opaque and window materials with physical
property validation.  No I/O or framework dependencies.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from .editing import Editable
from .enums import Roughness


@dataclass(frozen=True)
class EmbodiedCarbon(Editable):
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
class CarbonReference(Editable):
    """A manually authored carbon source with explicit unknown lifecycle modules.

    Module values are kg CO2e per ``unit``. The method is retained as supplied;
    no conversion to a different indicator or source methodology is implied.
    ``declared_unit`` records the source's original quantity when a factor has
    been normalized (for example one tonne to one kilogram).
    """

    identifier: str
    name: str
    url: str
    method: str
    unit: str
    modules: Mapping[str, float | None]
    proxy_for: str | None = None
    declared_unit: str | None = None
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("identifier", "name", "url", "method"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip() or value != value.strip():
                raise ValueError(f"Carbon reference {field_name} must be a non-empty string")
        try:
            location = urlsplit(self.url)
            valid_url = location.scheme in {"http", "https"} and bool(location.hostname)
        except ValueError:
            valid_url = False
        if not valid_url or any(character.isspace() for character in self.url):
            raise ValueError("Carbon reference url must be an HTTP(S) source URL")
        if not isinstance(self.unit, str) or self.unit not in {"kg", "m2", "m3", "item"}:
            raise ValueError("Carbon reference requires an explicit material quantity unit")
        if not isinstance(self.modules, Mapping) or not self.modules:
            raise ValueError("Carbon reference modules must be a non-empty mapping")
        modules = dict(self.modules)
        for module, value in modules.items():
            if not isinstance(module, str) or re.fullmatch(
                r"(?:A1A3|A[1-5]|B[1-7]|C[1-4]|D)(?:\.[1-9]\d*)?", module
            ) is None:
                raise ValueError(f"Invalid carbon reference lifecycle module: {module!r}")
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ValueError(f"Carbon reference {module} must be finite or unknown")
        for field_name in ("proxy_for", "declared_unit"):
            value = getattr(self, field_name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"Carbon reference {field_name} must be a non-empty string or None")
        if isinstance(self.notes, (str, Mapping)):
            raise ValueError("Carbon reference notes must be a sequence of strings")
        try:
            notes = tuple(self.notes)
        except TypeError as exc:
            raise ValueError("Carbon reference notes must be a sequence of strings") from exc
        if any(not isinstance(note, str) or not note.strip() for note in notes):
            raise ValueError("Carbon reference notes must contain non-empty strings")
        object.__setattr__(self, "modules", MappingProxyType(modules))
        object.__setattr__(self, "notes", notes)

    def __hash__(self):
        return hash((
            self.identifier, self.name, self.url, self.method, self.unit,
            tuple(sorted(self.modules.items())), self.proxy_for, self.declared_unit, self.notes,
        ))

    def __deepcopy__(self, memo):
        return self

    def to_dict(self) -> dict:
        """Return a JSON-compatible mapping."""
        return {
            "identifier": self.identifier,
            "name": self.name,
            "url": self.url,
            "method": self.method,
            "unit": self.unit,
            "modules": dict(self.modules),
            "proxy_for": self.proxy_for,
            "declared_unit": self.declared_unit,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> CarbonReference:
        """Rebuild a reference from ``to_dict`` output."""
        if not isinstance(data, Mapping):
            raise ValueError("Carbon reference must be a mapping")
        return cls(**data)

    def factors(self) -> dict[str, EnvironmentalFactor]:
        """Return known factors only; null placeholders never become zero."""
        source = f"{self.identifier} | {self.method} | {self.url}"
        if self.proxy_for is not None:
            source += f" | proxy for: {self.proxy_for}"
        return {
            module: EnvironmentalFactor(value, self.unit, module, source)
            for module, value in self.modules.items() if value is not None
        }


def _validate_carbon_reference(reference, boverket_id, embodied_carbon=None):
    if reference is not None:
        if not isinstance(reference, CarbonReference):
            raise ValueError("carbon_reference must be a CarbonReference record or None")
        if boverket_id is not None or embodied_carbon is not None:
            raise ValueError("External carbon_reference cannot also use a Boverket carbon source")


@dataclass(frozen=True)
class OpaqueMaterial(Editable):
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
    embodied_carbon: EmbodiedCarbon | None = None
    uuid: UUID = field(default_factory=uuid4)
    carbon_reference: CarbonReference | None = None

    def __post_init__(self) -> None:
        _validate_carbon_reference(self.carbon_reference, self.boverket_id, self.embodied_carbon)
        if not self.name:
            raise ValueError("Material name cannot be empty.")
        if isinstance(self.conductivity, bool) or not isinstance(self.conductivity, (int, float)) or not math.isfinite(self.conductivity) or self.conductivity <= 0:
            raise ValueError("Conductivity must be finite and positive.")
        if not (0.01 <= self.conductivity <= 400):
            raise ValueError("Conductivity outside realistic range (0.01-400 W/mK).")

        for name in ("density", "specific_heat"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        for name in ("thermal_absorptance", "solar_absorptance", "visible_absorptance"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be a finite fraction")
        if self.embodied_carbon is not None and not isinstance(self.embodied_carbon, EmbodiedCarbon):
            raise ValueError("embodied_carbon must be an EmbodiedCarbon record or None")
        object.__setattr__(self, "roughness", Roughness(self.roughness))
        object.__setattr__(self, "uuid", UUID(str(self.uuid)))

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
            "carbon_reference": self.carbon_reference.to_dict() if self.carbon_reference else None,
        }


@dataclass(frozen=True)
class WindowMaterial(Editable):
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
    embodied_carbon: EmbodiedCarbon | None = None
    uuid: UUID = field(default_factory=uuid4)
    carbon_reference: CarbonReference | None = None

    def __post_init__(self) -> None:
        _validate_carbon_reference(self.carbon_reference, self.boverket_id, self.embodied_carbon)
        if not self.name:
            raise ValueError("Material name cannot be empty.")
        if isinstance(self.conductivity, bool) or not isinstance(self.conductivity, (int, float)) or not math.isfinite(self.conductivity) or self.conductivity <= 0:
            raise ValueError("Conductivity must be finite and positive.")
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
            "carbon_reference": self.carbon_reference.to_dict() if self.carbon_reference else None,
        }


# Public name for the existing opaque physical material type; no parallel model.
Material = OpaqueMaterial


@dataclass(frozen=True)
class EnvironmentalFactor(Editable):
    """Source-labelled kg CO2e per explicit quantity unit and lifecycle module.

    Negative values are permitted (for example a reported biogenic factor).
    This definition does not choose assessment timing or calculate impacts.
    """

    value: float
    unit: str
    module: str
    source: str

    def __post_init__(self):
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)) or not math.isfinite(self.value):
            raise ValueError("Environmental factor value must be finite")
        if self.unit not in {"kg", "m2", "m3", "item", "kWh"}:
            raise ValueError("Environmental factor requires an explicit quantity unit")
        if not self.module.strip() or not self.source.strip():
            raise ValueError("Environmental factor module and source are required")

    def to_dict(self):
        """Return a JSON-compatible mapping."""
        return {"value": self.value, "unit": self.unit, "module": self.module, "source": self.source}

    @classmethod
    def from_dict(cls, data):
        """Rebuild a factor from ``to_dict`` output."""
        return cls(**data)
