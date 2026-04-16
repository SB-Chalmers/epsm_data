"""Layer entity placeholder.

Expected responsibilities:
- Layer composition model with area fractions and optional path metadata.
- Validation for fraction sums and thickness consistency.
- Metadata required by thermal calculation engine.
"""

from dataclasses import dataclass
from typing import Tuple
from epsm_data.domain.material import OpaqueMaterial, EmbodiedCarbon, WindowMaterialLayer, GlazingMaterial

@dataclass(frozen=True)
class Layer:
    name: str
    layer_code: str
    thickness: float
    materials: Tuple[Tuple[OpaqueMaterial, float, float], ...]  # (material, area_fraction, thickness)
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


    @property
    def r_value(self) -> float:
        """Effective thermal resistance [m2·K/W]. Calculated in thermal/layer_calc.py."""
        from epsm_data.thermal.layer_calc import compute_layer_r_value
        return compute_layer_r_value(self)
    
    @property
    def is_long_lived(self) -> bool:
        """True if all materials in the layer are long-lived."""
        return all(mat.is_long_lived for mat, _, _ in self.materials)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "layer_code": self.layer_code,
            "thickness": self.thickness,
            "is_composite": self.is_composite,
            "r_value": round(self.r_value, 6),
            "is_long_lived": self.is_long_lived,
            "materials": [
                {
                    "material name": mat.name,  # reference by name, not nested
                    "area fraction": frac,
                    "thickness": t,
                }
                for mat, frac, t in self.materials
            ],
        }
    
@dataclass(frozen=True)
class WindowConstruction:
    """An ordered stack of glazing and gas layers forming a window unit.
    
    Equivalent to Layer for opaque assemblies, but holds GlazingMaterial
    and GasMaterial instances instead of OpaqueMaterial.
    """
    name: str
    json_id: str                                    # Honeybee construction identifier
    boverket_id: str                                # for embodied carbon lookup
    materials: tuple[WindowMaterialLayer, ...]      # ordered pane/gas stack
    u_value_declared: float                         # W/m2·K — from Boverket/TABULA
    embodied_carbon: EmbodiedCarbon                 # at the construction level

    def __post_init__(self):
        if not self.name:
            raise ValueError("WindowConstruction name cannot be empty.")
        if not self.materials:
            raise ValueError(f"'{self.name}': must have at least one material.")
        if self.u_value_declared <= 0:
            raise ValueError(f"'{self.name}': u_value_declared must be positive.")

    @property
    def pane_count(self) -> int:
        """Number of glazing panes."""
        return sum(1 for m in self.materials if isinstance(m, GlazingMaterial))

    @property
    def total_thickness(self) -> float:
        """Total thickness of the window unit in metres."""
        return sum(m.thickness for m in self.materials)

    @property
    def is_long_lived(self) -> bool:
        return all(m.is_long_lived for m in self.materials)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "json_id": self.json_id,
            "boverket_id": self.boverket_id,
            "pane_count": self.pane_count,
            "total_thickness": self.total_thickness,
            "u_value_declared": self.u_value_declared,
            "is_long_lived": self.is_long_lived,
            "materials": [m.to_dict() for m in self.materials],
            "embodied_carbon": self.embodied_carbon.to_dict(),
        }
