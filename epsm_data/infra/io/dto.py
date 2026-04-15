"""Transport DataTransfer Objects for I/O operations.

These are lightweight frozen dataclasses that carry raw parsed data
from Excel/JSON sources into the domain construction layer.
No domain logic or validation beyond basic parsing lives here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")


# ── Result container ──────────────────────────────────────────────


@dataclass
class ReadResult(Generic[T]):
    """Pairs loaded records with skipped-row diagnostics."""

    records: list[T] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (id, reason)


# ── Excel DTOs ────────────────────────────────────────────────────


@dataclass(frozen=True)
class MaterialRow:
    """Row from the Opaque_Materials sheet."""

    name: str
    boverket_id: str
    honeybee_id: str


@dataclass(frozen=True)
class LayerMaterialSlot:
    """One material slot within a layer row (up to 3 per layer)."""

    material_name: str
    area_fraction: float | None  # None when the spreadsheet cell is blank


@dataclass(frozen=True)
class LayerRow:
    """Row from the Layers sheet."""

    layer_code: str
    thickness: float
    is_composite: bool
    materials: tuple[LayerMaterialSlot, ...]


@dataclass(frozen=True)
class ComponentLayerRef:
    """One layer reference within a component group."""

    layer_code: str
    layer_index: int


@dataclass(frozen=True)
class ComponentRow:
    """Aggregated component from the Components sheet (multiple rows → one DTO)."""

    component_code: str
    archetype: str
    application: str  # raw string, mapped to enum in domain layer
    shearing_layer: str  # raw string
    layers: tuple[ComponentLayerRef, ...]


@dataclass(frozen=True)
class ElementRow:
    """Row from the Elements sheet."""

    element_code: str
    element_type: str
    archetype: str
    construction_year: int
    component_codes: tuple[str, ...]


@dataclass(frozen=True)
class BuildingRow:
    """Row from the Building sheet."""

    archetype: str
    construction_year: int
    multiple_ext_walls: bool
    element_assignments: tuple[tuple[str, str], ...]  # (role, element_code)


# ── JSON DTOs ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class OpaqueMaterialProps:
    """Material properties from opaque_material.json (EnergyMaterial)."""

    identifier: str
    material_type: str
    roughness: str
    thickness: float
    conductivity: float
    density: float
    specific_heat: float
    thermal_absorptance: float
    solar_absorptance: float
    visible_absorptance: float


@dataclass(frozen=True)
class WindowGlazingProps:
    """Glazing properties from window_material.json (EnergyWindowMaterialGlazing)."""

    identifier: str
    material_type: str
    thickness: float
    conductivity: float
    solar_transmittance: float
    solar_reflectance: float
    solar_reflectance_back: float
    visible_transmittance: float
    visible_reflectance: float
    visible_reflectance_back: float
    infrared_transmittance: float
    emissivity: float
    emissivity_back: float
    dirt_correction: float
    solar_diffusing: bool


@dataclass(frozen=True)
class WindowGasProps:
    """Gas-layer properties from window_material.json (EnergyWindowMaterialGas)."""

    identifier: str
    material_type: str
    thickness: float
    gas_type: str
