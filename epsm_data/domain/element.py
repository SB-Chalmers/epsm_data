"""Element domain entity.

An Element aggregates components into a full envelope or partition
assembly with boundary-condition metadata and TABULA reference
validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Tuple

from .component import Component
from .enums import BuildingElement

# TABULA reference U-values by archetype key and element type.
TABULA_CMF: dict[str, dict[str, float]] = {
    "CMF_1940": {"roof": 0.36, "wall": 0.58, "window": 2.22, "floor": 0.32, "basement_wall": 0.70},
    "CMF_1950": {"roof": 0.36, "wall": 0.58, "window": 2.22, "floor": 0.32, "basement_wall": 0.70},
    "CMF_1960": {"roof": 0.20, "wall": 0.41, "window": 2.22, "floor": 0.26, "basement_wall": 0.70},
    "CMF_1970": {"roof": 0.20, "wall": 0.41, "window": 2.22, "floor": 0.26, "basement_wall": 0.70},
    "CMF_1980": {"roof": 0.17, "wall": 0.33, "window": 2.04, "floor": 0.27, "basement_wall": 0.70},
    "CMF_1990": {"roof": 0.15, "wall": 0.22, "window": 1.80, "floor": 0.24, "basement_wall": 0.70},
}


@dataclass(frozen=True)
class Element:
    """A full envelope/partition element composed of components."""

    name: str
    archetype: str
    age: int
    components: Tuple[Component, ...]
    application: BuildingElement

    TABULA_TYPE_MAP: ClassVar[dict[BuildingElement, str]] = {
        BuildingElement.EXT_WALL: "wall",
        BuildingElement.EXT_WALL_LOW: "wall",
        BuildingElement.EXT_WALL_MEDIUM: "wall",
        BuildingElement.EXT_WALL_HIGH: "wall",
        BuildingElement.GROUND_FLOOR: "floor",
        BuildingElement.ROOF: "roof",
    }

    def __post_init__(self) -> None:
        if not self.components:
            raise ValueError(f"Element '{self.name}': missing components.")

    @property
    def r_total(self) -> float:
        """Total thermal resistance including boundary resistances [m2 K/W]."""
        rsi = 0.13
        # Interior elements get symmetric boundary; exterior get 0.04
        rse = 0.13 if self.application in (
            BuildingElement.INT_WALL_LOADBEARING,
            BuildingElement.INT_WALL_NONLOADBEARING,
            BuildingElement.INTERMEDIATE_FLOOR,
        ) else 0.04
        return rsi + sum(c.r_sum for c in self.components) + rse

    @property
    def u_value(self) -> float:
        """Overall U-value [W/m2 K]."""
        if self.r_total <= 0:
            raise ValueError(f"Element '{self.name}': R-value <= 0.")
        return 1.0 / self.r_total

    @property
    def total_components(self) -> int:
        return len(self.components)

    def _match_tabula(self, tabula_data: dict[str, dict[str, float]]) -> tuple[str, str] | None:
        """Resolve archetype key and element type in TABULA data."""
        name_upper = self.name.upper()
        matched_archetype = next(
            (k for k in tabula_data if k.upper() in name_upper), None
        )
        if matched_archetype is None:
            return None
        matched_type = self.TABULA_TYPE_MAP.get(self.application)
        if matched_type is None:
            return None
        return matched_archetype, matched_type

    @property
    def tabula_u_value(self) -> float | None:
        """Reference U-value from TABULA, or None if no match."""
        match = self._match_tabula(TABULA_CMF)
        if match is None:
            return None
        archetype_key, element_type = match
        return TABULA_CMF[archetype_key][element_type]

    def check_tabula(
        self,
        tabula_data: dict[str, dict[str, float]] | None = None,
        threshold: float = 0.2,
    ) -> str | None:
        """Return a warning string if U-value is outside TABULA tolerance band."""
        data = tabula_data if tabula_data is not None else TABULA_CMF
        match = self._match_tabula(data)
        if match is None:
            return None
        archetype_key, element_type = match
        tabula_u = data[archetype_key][element_type]
        if self.u_value > tabula_u * (1 + threshold) or self.u_value < tabula_u * (1 - threshold):
            return (
                f"U-value {self.u_value:.4f} outside TABULA range "
                f"(+/-{threshold * 100:.0f}%) of {tabula_u} "
                f"for {archetype_key} {element_type}"
            )
        return None

    @property
    def tabula_warning(self) -> str | None:
        return self.check_tabula()

    def to_dict(self) -> dict:
        warning = self.tabula_warning
        return {
            "name": self.name,
            "archetype": self.archetype,
            "age": self.age,
            "application": self.application.value,
            "u_value": round(self.u_value, 6),
            "tabula_u_value": self.tabula_u_value,
            "tabula_warning": warning if warning else "Pass",
            "r_total": round(self.r_total, 6),
            "total_components": self.total_components,
            "components": [comp.name for comp in self.components],
        }
