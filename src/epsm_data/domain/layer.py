"""Layer domain entity.

A Layer is an ordered material composition within a component.
Each material slot has an area fraction; composite layers have >= 2.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Tuple

from .editing import Editable
from .material import OpaqueMaterial


def resolve_fractions(raw: list[float | None]) -> list[float]:
    """Divide the unassigned area equally among missing fractions.

    Parameters
    ----------
    raw : list of float or None
        Area fractions with None for unassigned slots.

    Returns
    -------
    list of float
        Completed fractions. Layer validation checks bounds and the final sum.

    Raises
    ------
    ValueError
        Known fractions exceed one while unassigned slots remain.
    """
    missing = [i for i, f in enumerate(raw) if f is None]
    if not missing:
        return list(raw)  # type: ignore[arg-type]
    known_sum = sum(f for f in raw if f is not None)
    if known_sum > 1.0:
        raise ValueError(f"Known fractions sum to {known_sum:.4f}, exceeds 1.0.")
    fill = (1.0 - known_sum) / len(missing)
    result = list(raw)
    for i in missing:
        result[i] = fill
    return result  # type: ignore[return-value]


@dataclass(frozen=True)
class LayerMaterial(Editable):
    """Describe one material's share of a layer.

    Parameters
    ----------
    material : OpaqueMaterial
        Resolved thermal and carbon properties.
    area_fraction : float
        Parallel area share between zero and one.
    thickness : float
        Material thickness in metres, positive and finite.
    """

    material: OpaqueMaterial
    area_fraction: float
    thickness: float

    def __post_init__(self) -> None:
        if not isinstance(self.material, OpaqueMaterial):
            raise ValueError("Layer materials must reference a Material")
        if isinstance(self.area_fraction, bool) or not isfinite(self.area_fraction) or not 0 <= self.area_fraction <= 1:
            raise ValueError("Area fraction must be finite and between zero and one")
        if isinstance(self.thickness, bool) or not isfinite(self.thickness) or self.thickness <= 0:
            raise ValueError("Material slot thickness must be finite and positive")


@dataclass(frozen=True)
class Layer(Editable):
    """Construction layer with homogeneous or parallel material composition.

    Parameters
    ----------
    name, layer_code : str
        Display label and reference identity.
    thickness : float
        Shared layer depth in metres.
    materials : tuple of LayerMaterial
        Material shares summing to one within 0.001.
    is_composite : bool, optional
        True exactly when more than one material is present.

    Notes
    -----
    Constituent depths are preserved for physical quantities, including unequal
    depths. Thermal resistance is available only when every constituent spans
    the shared layer depth; other cases need an explicit thermal representation.
    """

    name: str
    layer_code: str
    thickness: float
    materials: Tuple[LayerMaterial, ...]
    is_composite: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.thickness, bool) or not isfinite(self.thickness) or self.thickness <= 0:
            raise ValueError(f"Layer '{self.name}': thickness must be > 0.")
        object.__setattr__(self, "materials", tuple(self.materials))
        if any(not isinstance(m, LayerMaterial) for m in self.materials):
            raise ValueError("materials must contain LayerMaterial records")
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
        Composite: shared depth divided by area-weighted conductivity.

        Raises
        ------
        ValueError
            Constituent depths differ from the layer depth. Their physical
            quantities remain usable, but this thermal equivalencing is undefined.
        """
        if any(abs(m.thickness - self.thickness) > 1e-9 for m in self.materials):
            raise ValueError("Thermal equivalencing does not support unequal constituent depths")
        d = self.thickness

        if len(self.materials) == 1:
            lam = self.materials[0].material.conductivity
            if lam <= 0:
                raise ValueError(f"Invalid conductivity ({lam}) in layer '{self.name}'")
            return d / lam

        avg_lambda = sum(m.material.conductivity * m.area_fraction for m in self.materials)
        if avg_lambda <= 0:
            raise ValueError(f"Invalid avg conductivity ({avg_lambda}) in layer '{self.name}'")

        r_lambda = d / avg_lambda
        total_u = sum((m.material.conductivity / d) * m.area_fraction for m in self.materials)
        r_u = 1 / total_u if total_u > 0 else 0.0

        return 0.5 * (r_lambda + r_u)

    def to_dict(self) -> dict:
        """Return layer properties and material-name references.

        Returns
        -------
        dict
            JSON-compatible values. Referenced objects remain named links;
            use archetype_to_dict for the complete resolved hierarchy.
        """
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
