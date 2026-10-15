# SPDX-License-Identifier: MIT
"""Portable envelope assumptions with explicit flow reference bases."""

from dataclasses import dataclass
from math import isfinite

from .editing import Editable


def _text_tuple(value, label):
    if isinstance(value, str):
        raise ValueError(f"{label} must be a sequence of nonempty text")
    try:
        result = tuple(value)
    except TypeError as exc:
        raise ValueError(f"{label} must be a sequence of nonempty text") from exc
    if any(not isinstance(item, str) or not item.strip() for item in result):
        raise ValueError(f"{label} must contain nonempty text")
    return result


@dataclass(frozen=True, repr=False)
class EnvelopePerformance(Editable):
    """Sourced infiltration and thermal-bridge assumptions, independent of geometry.

    Parameters
    ----------
    infiltration_ach : float or None
        Air changes per hour; basis is ``conditioned_volume`` or
        ``tabula_reference_volume``. The latter requires an explicit source volume
        and reference area during building application; it is never silently
        interpreted as model-volume ACH.
    infiltration_l_s_m2 : float or None
        Litres per second per square metre; basis is ``Atemp`` or
        ``conditioned_floor_area``. Supply at most one infiltration rate.
    infiltration_reference_basis : str or None
        Required when either rate is supplied. No conversion is performed here.
    thermal_bridge_uplift_fraction : float or None
        Nonnegative uplift relative to nominal transmission. Unknown is None;
        zero explicitly means no uplift. Core owns its physical application.
    source_references, notes : tuple of str
        Source identifiers and declared modelling choices, retained in exchange.

    Notes
    -----
    Supplied numbers must be finite and nonnegative. Empty definitions remain
    valid incomplete inputs. Ground conditions, weather and installed ventilation
    topology belong to the Building. Construction and inspection perform no I/O.
    """

    infiltration_ach: float | None = None
    infiltration_l_s_m2: float | None = None
    infiltration_reference_basis: str | None = None
    thermal_bridge_uplift_fraction: float | None = None
    source_references: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def __post_init__(self):
        for name in ("infiltration_ach", "infiltration_l_s_m2", "thermal_bridge_uplift_fraction"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
                or value < 0
            ):
                raise ValueError(f"{name} must be finite and nonnegative, or None")
        if self.infiltration_ach is not None and self.infiltration_l_s_m2 is not None:
            raise ValueError("Supply only one infiltration rate")
        basis = self.infiltration_reference_basis
        if basis is not None and basis not in (
            "conditioned_volume",
            "tabula_reference_volume",
            "Atemp",
            "conditioned_floor_area",
        ):
            raise ValueError("Unsupported infiltration reference basis")
        if self.infiltration_ach is not None and basis not in (
            "conditioned_volume",
            "tabula_reference_volume",
        ):
            raise ValueError("ACH requires conditioned_volume or tabula_reference_volume basis")
        if self.infiltration_l_s_m2 is not None and basis not in (
            "Atemp",
            "conditioned_floor_area",
        ):
            raise ValueError("Area infiltration requires Atemp or conditioned_floor_area basis")
        for name in ("source_references", "notes"):
            object.__setattr__(self, name, _text_tuple(getattr(self, name), name))

    def to_dict(self):
        """Return detached portable values without conversions or I/O."""
        return {
            "infiltration_ach": self.infiltration_ach,
            "infiltration_l_s_m2": self.infiltration_l_s_m2,
            "infiltration_reference_basis": self.infiltration_reference_basis,
            "thermal_bridge_uplift_fraction": self.thermal_bridge_uplift_fraction,
            "source_references": list(self.source_references),
            "notes": list(self.notes),
        }

    def summary(self):
        """Inspect complete loaded assumptions and provenance, without I/O."""
        return self.to_dict()

    def __repr__(self):
        rate = (
            self.infiltration_ach if self.infiltration_ach is not None else self.infiltration_l_s_m2
        )
        kind = "ach" if self.infiltration_ach is not None else "l_s_m2"
        rate_text = f"{rate:.6g}" if rate is not None else "unknown"
        bridge = self.thermal_bridge_uplift_fraction
        bridge_text = f"{bridge:.6g}" if bridge is not None else "unknown"
        return (
            f"EnvelopePerformance({kind}={rate_text}, basis={self.infiltration_reference_basis!r}, "
            f"bridges={bridge_text}, sources={len(self.source_references)})"
        )

    __str__ = __repr__

    @classmethod
    def from_dict(cls, data):
        """Restore a definition without catalogue lookup or geometry inference."""
        return cls(**data)
