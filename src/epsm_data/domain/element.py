"""Element domain entity.

An Element aggregates components into a full envelope or partition
assembly with boundary-condition metadata.

WindowElement models glazing — currently via simple U/SHGC properties,
extensible to full glazing-layer construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

from .component import Component
from .enums import BuildingElement


@dataclass(frozen=True)
class Element:
    """Envelope or partition construction.

    Parameters
    ----------
    name, archetype : str
        Element identity and owning archetype label.
    age : int
        Historical field name for the construction calendar year, not duration.
    components : tuple of Component
        Non-empty component stack ordered outside to inside.
    application : BuildingElement
        Envelope or partition role determining boundary resistance.
    """

    name: str
    archetype: str
    age: int
    components: Tuple[Component, ...]
    application: BuildingElement

    def __post_init__(self) -> None:
        if not self.components:
            raise ValueError(f"Element '{self.name}': missing components.")

    @property
    def r_total(self) -> float:
        """Total thermal resistance including boundary resistances [m2 K/W]."""
        rsi = 0.13
        # Interior elements get symmetric boundary; exterior get 0.04
        rse = (
            0.13
            if self.application
            in (
                BuildingElement.INT_WALL_LOADBEARING,
                BuildingElement.INT_WALL_NONLOADBEARING,
                BuildingElement.INTERMEDIATE_FLOOR,
            )
            else 0.04
        )
        return rsi + sum(c.r_sum for c in self.components) + rse

    @property
    def u_value(self) -> float:
        """Overall U-value [W/m2 K]."""
        if self.r_total <= 0:
            raise ValueError(f"Element '{self.name}': R-value <= 0.")
        return 1.0 / self.r_total

    @property
    def total_components(self) -> int:
        """Number of resolved components in this element."""
        return len(self.components)

    def to_dict(self) -> dict:
        """Return element properties and any component-name references.

        Returns
        -------
        dict
            JSON-compatible values. Referenced objects remain named links;
            use archetype_to_dict for the complete resolved hierarchy.
        """
        return {
            "name": self.name,
            "archetype": self.archetype,
            "age": self.age,
            "application": self.application.value,
            "u_value": round(self.u_value, 6),
            "r_total": round(self.r_total, 6),
            "total_components": self.total_components,
            "components": [comp.name for comp in self.components],
        }


# ---------------------------------------------------------------------------
# Window element — simple glazing system, extensible to layered
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WindowElement:
    """Window envelope element.

    Parameters
    ----------
    name, archetype : str
        Element identity and owning archetype label.
    u_value : float
        Whole-window thermal transmittance in W/(m² K).
    shgc : float
        Solar heat gain coefficient in (0, 1].
    vt : float, optional
        Visible transmittance in (0, 1], default 0.65.
    boverket_id : int, optional
        Legacy source reference. No source is fetched or validated.
    """

    name: str
    archetype: str
    u_value: float  # whole-window U [W/(m²·K)]
    shgc: float  # solar heat gain coefficient
    vt: float = 0.65  # visible transmittance (default for 2-pane clear)
    boverket_id: int | None = None  # Klimatdatabas resource ID
    # Future: glazing_layers: tuple[GlazingLayer, ...] = ()

    application: BuildingElement = field(
        default=BuildingElement.WINDOW,
        init=False,
    )

    def __post_init__(self) -> None:
        if self.u_value <= 0:
            raise ValueError(f"WindowElement '{self.name}': U-value must be positive.")
        if not 0 < self.shgc <= 1:
            raise ValueError(f"WindowElement '{self.name}': SHGC must be in (0, 1].")
        if not 0 < self.vt <= 1:
            raise ValueError(f"WindowElement '{self.name}': VT must be in (0, 1].")

    def to_dict(self) -> dict:
        """Return element properties and any component-name references.

        Returns
        -------
        dict
            JSON-compatible values. Referenced objects remain named links;
            use archetype_to_dict for the complete resolved hierarchy.
        """
        return {
            "name": self.name,
            "archetype": self.archetype,
            "application": self.application.value,
            "u_value": round(self.u_value, 6),
            "shgc": round(self.shgc, 4),
            "vt": round(self.vt, 4),
            "boverket_id": self.boverket_id,
        }
