"""Element entity placeholder.

Expected responsibilities:
- Aggregation of components into envelope/internal wall elements.
- Boundary-condition metadata used by thermal module.
- Tabula/reference lookup keys and validation hooks.
"""

from dataclasses import dataclass, field
from typing import Tuple, ClassVar
from epsm_data.domain.enums import BuildingElement
from epsm_data.domain.component import Components
from epsm_data.thermal.standards import TABULA_CMF
from epsm_data.domain.layer import WindowConstruction

@dataclass(frozen=True)
class Elements:
    name: str
    archetype: str
    age: int
    components: Tuple[Components, ...]
    application: BuildingElement

    TABULA_TYPE_MAP: ClassVar[dict] = {
        BuildingElement.EXT_WALL:        "wall",
        BuildingElement.EXT_WALL_LOW:    "wall",
        BuildingElement.EXT_WALL_MEDIUM: "wall",
        BuildingElement.EXT_WALL_HIGH:   "wall",
        BuildingElement.GROUND_FLOOR:    "floor",
        # BuildingElement.BASEMENT_FLOOR:  "floor",
        BuildingElement.ROOF:            "roof",
    }

    def __post_init__(self):
        if not self.components:
            raise ValueError(f"Element '{self.name}': missing components.")

    @property
    def r_total(self) -> float:
        """Total thermal resistance including surface resistances [m2·K/W]. See thermal/element_calc.py."""
        from epsm_data.thermal.element_calc import compute_r_total
        return compute_r_total(self)

    @property
    def u_value(self) -> float:
        """Thermal transmittance [W/m2·K]. See thermal/element_calc.py."""
        from epsm_data.thermal.element_calc import compute_u_value
        return compute_u_value(self)
        
    @property
    def total_components(self) -> int:
        """Number of components in this element."""
        return len(self.components)

    def match_tabula(self, tabula_data: dict) -> tuple[str, str] | None:
        """Resolve archetype and element type keys for a Tabula lookup. See thermal/standards.py."""
        from epsm_data.thermal.standards import match_tabula
        return match_tabula(self, tabula_data)

    @property
    def tabula_u_value(self) -> float | None:
        """Reference U-value from TABULA_CMF, or None if no match."""
        from epsm_data.thermal.standards import tabula_u_value
        return tabula_u_value(self)

    @property
    def tabula_warning(self) -> str | None:
        """Validation warning if U-value falls outside TABULA_CMF tolerance, or None if pass."""
        from epsm_data.thermal.standards import check_tabula
        return check_tabula(self, TABULA_CMF)

    @property
    def is_long_lived(self) -> bool:
        """True if all components in the element are long-lived."""
        return all(c.is_long_lived for c in self.components)

    def to_dict(self) -> dict:
        tabula = self.tabula_warning
        return {
            "name": self.name,
            "archetype": self.archetype,
            "age": self.age,
            "application": self.application.value,
            "u_value": round(self.u_value, 6),
            "tabula_u_value": self.tabula_u_value,
            "tabula_warning": tabula if tabula else "Pass",
            "r_total": round(self.r_total, 6),
            "total_components": self.total_components,
            "components": [comp.name for comp in self.components],
        }
    
@dataclass(frozen=True)
class WindowElement:
    """A window element — fits the same role as Elements in BuildingArchetype.
    
    Uses a declared U-value rather than computing from layer stack,
    since glazing thermal calculations require ISO 15099 which is
    beyond the scope of the thermal/ module for now.
    """
    name: str
    archetype: str
    age: int
    application: BuildingElement    # always BuildingElement.WINDOW
    construction: WindowConstruction

    def __post_init__(self):
        if not self.name:
            raise ValueError("WindowElement name cannot be empty.")
        if self.application != BuildingElement.WINDOW:
            raise ValueError(
                f"'{self.name}': WindowElement application must be WINDOW, "
                f"got {self.application}."
            )

    @property
    def u_value(self) -> float:
        """Declared U-value from Boverket/TABULA [W/m2·K]."""
        return self.construction.u_value_declared

    @property
    def is_long_lived(self) -> bool:
        return self.construction.is_long_lived

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "archetype": self.archetype,
            "age": self.age,
            "application": self.application.value,
            "u_value": round(self.u_value, 6),
            "tabula_u_value": self.construction.u_value_declared,
            "tabula_warning": "Pass",
            "pane_count": self.construction.pane_count,
            "total_thickness": self.construction.total_thickness,
            "construction": self.construction.json_id,  # reference by id, not nested
        }