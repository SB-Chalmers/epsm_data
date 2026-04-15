"""Layer domain entity.

A Layer is an ordered material composition within a component.
Each material slot has an area fraction; composite layers have >= 2.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from .material import OpaqueMaterial


@dataclass(frozen=True)
class LayerMaterial:
    """One material slot within a layer."""

    material: OpaqueMaterial
    area_fraction: float
    thickness: float


@dataclass(frozen=True)
class Layer:
    """A single construction layer with one or more materials."""

    name: str
    layer_code: str
    thickness: float
    materials: Tuple[LayerMaterial, ...]
    is_composite: bool = False

    def __post_init__(self) -> None:
        if self.thickness <= 0:
            raise ValueError(f"Layer '{self.name}': thickness must be > 0.")
        if not self.materials:
            raise ValueError(f"Layer '{self.name}': must have at least one material.")

        total_frac = sum(m.area_fraction for m in self.materials)
        if not (0.999 <= total_frac <= 1.001):
            raise ValueError(
                f"Layer '{self.name}': area fractions sum to {total_frac:.4f}, expected 1.0."
            )

        if self.is_composite and len(self.materials) < 2:
            raise ValueError(
                f"Layer '{self.name}': marked composite but only {len(self.materials)} material."
            )
        if not self.is_composite and len(self.materials) > 1:
            raise ValueError(
                f"Layer '{self.name}': {len(self.materials)} materials but not marked composite."
            )

    @property
    def r_value(self) -> float:
        """Effective thermal resistance [m2 K/W].

        Single material: R = d / lambda.
        Composite: weighted average of lambda-method and U-value-method.
        """
        d = self.thickness

        if len(self.materials) == 1:
            lam = self.materials[0].material.conductivity
            if lam <= 0:
                raise ValueError(f"Invalid conductivity ({lam}) in layer '{self.name}'")
            return d / lam

        avg_lambda = sum(
            m.material.conductivity * m.area_fraction for m in self.materials
        )
        if avg_lambda <= 0:
            raise ValueError(f"Invalid avg conductivity ({avg_lambda}) in layer '{self.name}'")

        r_lambda = d / avg_lambda
        total_u = sum(
            (m.material.conductivity / d) * m.area_fraction for m in self.materials
        )
        r_u = 1 / total_u if total_u > 0 else 0.0

        return 0.5 * (r_lambda + r_u)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "layer_code": self.layer_code,
            "thickness": self.thickness,
            "is_composite": self.is_composite,
            "r_value": round(self.r_value, 6),
            "materials": [
                {
                    "material_name": m.material.name,
                    "area_fraction": m.area_fraction,
                    "thickness": m.thickness,
                }
                for m in self.materials
            ],
        }
