"""Material entity placeholder.

Expected responsibilities:
- Opaque and window material domain definitions.
- Physical properties validation (conductivity, density, etc.).
- Service-life metadata hooks for lifecycle simulation.

- Embodied carbon domain definition ?
- Window will come
"""

from dataclasses import dataclass, field
from epsm_data.domain.enums import Roughness
from uuid import UUID, uuid4


@dataclass(frozen=True)
class EmbodiedCarbon:
    name: str
    resource_id: str
    boverket_name: str
    A1_A3_conservative: float   # kg CO₂e/kg
    A1_A3_typical: float        # kg CO₂e/kg
    A4_transport: float         # kg CO₂e/kg
    A5_conservative: float      # kg CO₂e/kg
    conservative_factor: float  # multiplier (e.g. 1.25)
    conversion_factor: float    # kg/m³
    technical_service_life: str # years — may contain symbols e.g. ">50", "<25"
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
                f"'{self.name}': A1-A3 conservative value cannot be lower than typical value."
            )

    @property
    def service_life_years(self) -> int | None:
        """Parse technical_service_life to int where possible.
        Returns None if unparseable (e.g. '>50', 'N/A').
        """
        cleaned = str(self.technical_service_life).strip().lstrip("<>~≥≤ ")
        try:
            return int(float(cleaned))
        except ValueError:
            return None

    @property
    def is_long_lived(self) -> bool:
        """True if service life is 50+ years, or unparseable (assume durable)."""
        years = self.service_life_years
        return years is None or years >= 50


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
            "is_long_lived": self.is_long_lived,
            "service_life_years": self.service_life_years,
        }

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
        
    @property
    def service_life_years(self) -> int | None:
        """Parsed service life in years, or None if unparseable. See EmbodiedCarbon.service_life_years."""
        return self.embodied_carbon.service_life_years

    @property
    def technical_service_life(self) -> str:
        """Raw service life string from Boverket API (may contain symbols e.g. '>50')."""
        return self.embodied_carbon.technical_service_life
    
    @property
    def is_long_lived(self) -> bool:
        """True if service life is 50+ years or unparseable. See EmbodiedCarbon.is_long_lived."""
        return self.embodied_carbon.is_long_lived
    
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
            "is_long_lived": self.is_long_lived,
            "embodied_carbon": self.embodied_carbon.to_dict(),
        }
    

@dataclass(frozen=True)
class GlazingMaterial:
    """A glazing pane layer — EnergyWindowMaterialGlazing in Honeybee.
    
    Holds optical and thermal properties of a single glass pane.
    """
    name: str
    json_id: str
    thickness: float                # m
    solar_transmittance: float      # 0-1
    solar_reflectance: float        # 0-1 front
    solar_reflectance_back: float   # 0-1 back
    visible_transmittance: float    # 0-1
    visible_reflectance: float      # 0-1
    visible_reflectance_back: float # 0-1
    infrared_transmittance: float   # 0-1
    emissivity: float               # 0-1 front
    emissivity_back: float          # 0-1 back
    conductivity: float             # W/m·K
    dirt_correction: float          # typically 1.0
    solar_diffusing: bool
    embodied_carbon: EmbodiedCarbon
    uuid: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        if not self.name:
            raise ValueError("GlazingMaterial name cannot be empty.")
        if self.conductivity <= 0:
            raise ValueError(f"'{self.name}': conductivity must be positive.")
        for attr in ("solar_transmittance", "solar_reflectance",
                     "solar_reflectance_back", "visible_transmittance",
                     "visible_reflectance", "visible_reflectance_back",
                     "emissivity", "emissivity_back"):
            val = getattr(self, attr)
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"'{self.name}': {attr} must be between 0 and 1.")

    @property
    def service_life_years(self) -> int | None:
        return self.embodied_carbon.service_life_years

    @property
    def is_long_lived(self) -> bool:
        return self.embodied_carbon.is_long_lived

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "uuid": str(self.uuid),
            "json_id": self.json_id,
            "type": "GlazingMaterial",
            "thickness": self.thickness,
            "solar_transmittance": self.solar_transmittance,
            "solar_reflectance": self.solar_reflectance,
            "solar_reflectance_back": self.solar_reflectance_back,
            "visible_transmittance": self.visible_transmittance,
            "visible_reflectance": self.visible_reflectance,
            "visible_reflectance_back": self.visible_reflectance_back,
            "infrared_transmittance": self.infrared_transmittance,
            "emissivity": self.emissivity,
            "emissivity_back": self.emissivity_back,
            "conductivity": self.conductivity,
            "dirt_correction": self.dirt_correction,
            "solar_diffusing": self.solar_diffusing,
            "embodied_carbon": self.embodied_carbon.to_dict(),
        }


@dataclass(frozen=True)
class GasMaterial:
    """A gas gap layer — EnergyWindowMaterialGas in Honeybee.
    
    Represents the gas cavity between glazing panes.
    No embodied carbon — gas gaps have negligible impact.
    """
    name: str
    json_id: str
    thickness: float    # m
    gas_type: str       # e.g. "Air", "Argon", "Krypton"
    uuid: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        if not self.name:
            raise ValueError("GasMaterial name cannot be empty.")
        if self.thickness <= 0:
            raise ValueError(f"'{self.name}': thickness must be positive.")

    @property
    def is_long_lived(self) -> bool:
        """Gas gaps are considered durable — same lifetime as the window unit."""
        return True

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "uuid": str(self.uuid),
            "json_id": self.json_id,
            "type": "GasMaterial",
            "thickness": self.thickness,
            "gas_type": self.gas_type,
        }
    
# Union type for anything that can appear in a window layer stack
WindowMaterialLayer = GlazingMaterial | GasMaterial




