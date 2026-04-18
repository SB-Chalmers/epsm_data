"""Building archetype entity.

The BuildingArchetype is the central stateful container in THIS library.
It is a reusable template — NOT a geolocated building instance.

A downstream library (e.g. building_sim) instantiates a
GeolocatedBuilding by combining:

    GeolocatedBuilding = BuildingArchetype + FootprintGeometry + SiteContext

The archetype exposes a clean, serializable consumption contract that
downstream libraries consume without importing epsm_data internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from .element import Element, WindowElement
from .enums import BuildingElement


@dataclass(frozen=True)
class ConstructionSet:
    """Immutable snapshot of the archetype's physical makeup at one point."""

    version_id: UUID
    valid_from_year: int
    elements: dict[BuildingElement, Element | WindowElement]  # role -> element

    def to_dict(self) -> dict:
        return {
            "version_id": str(self.version_id),
            "valid_from_year": self.valid_from_year,
            "elements": {
                role.value: elem.to_dict() for role, elem in self.elements.items()
            },
        }


@dataclass(frozen=True)
class RenovationEvent:
    """One applied renovation measure with provenance."""

    measure_id: str  # catalog key, e.g. "ventilation.install_ftx"
    applied_year: int
    trigger: str  # "end_of_life" | "policy" | "piggyback" | "user"
    removed_components: tuple[str, ...]  # component names removed
    added_components: tuple[str, ...]  # component names added
    construction_set_before: UUID
    construction_set_after: UUID
    cost_sek: float | None = None
    embodied_carbon_delta: float | None = None

    def to_dict(self) -> dict:
        return {
            "measure_id": self.measure_id,
            "applied_year": self.applied_year,
            "trigger": self.trigger,
            "removed_components": list(self.removed_components),
            "added_components": list(self.added_components),
            "construction_set_before": str(self.construction_set_before),
            "construction_set_after": str(self.construction_set_after),
            "cost_sek": self.cost_sek,
            "embodied_carbon_delta": self.embodied_carbon_delta,
        }


@dataclass(frozen=True)
class BuildingArchetype:
    """Central container: archetype identity + construction set + renovation log."""

    archetype_id: str  # e.g. "CMF_1950"
    display_name: str
    construction_year: int
    building_typology: str  # e.g. "multi_family" | "single_family"
    construction_set: ConstructionSet
    renovation_log: tuple[RenovationEvent, ...] = ()

    def __post_init__(self) -> None:
        if not self.construction_set.elements:
            raise ValueError(
                f"Building '{self.archetype_id}': construction set has no elements."
            )

    @property
    def current_year(self) -> int:
        """Latest year reflected in the archetype state."""
        if self.renovation_log:
            return max(e.applied_year for e in self.renovation_log)
        return self.construction_year

    def with_renovation(
        self,
        event: RenovationEvent,
        new_construction_set: ConstructionSet,
    ) -> BuildingArchetype:
        """Return a new archetype with the renovation applied."""
        return BuildingArchetype(
            archetype_id=self.archetype_id,
            display_name=self.display_name,
            construction_year=self.construction_year,
            building_typology=self.building_typology,
            construction_set=new_construction_set,
            renovation_log=self.renovation_log + (event,),
        )

    @property
    def envelope_u_values(self) -> dict[str, float]:
        """Current U-values keyed by normalized role.

        Exterior wall variants (LOW/MEDIUM/HIGH) are averaged into a
        single 'wall' key.  A single EXT_WALL also maps to 'wall'.
        """
        result: dict[str, float] = {}
        wall_values: list[float] = []

        for role, elem in self.construction_set.elements.items():
            if role == BuildingElement.WINDOW:
                result["WINDOW"] = elem.u_value
            elif role.is_ext_wall:
                wall_values.append(elem.u_value)
            else:
                result[role.value] = elem.u_value

        if wall_values:
            result["wall"] = sum(wall_values) / len(wall_values)

        return result

    @property
    def window(self) -> WindowElement | None:
        """Shortcut to the window element, if present."""
        elem = self.construction_set.elements.get(BuildingElement.WINDOW)
        return elem if isinstance(elem, WindowElement) else None

    @property
    def total_elements(self) -> int:
        return len(self.construction_set.elements)

    def to_consumption_contract(self) -> dict:
        """Export archetype state as a flat, serializable dict.

        Self-contained — no object references back into epsm_data.
        """
        return {
            "archetype_id": self.archetype_id,
            "display_name": self.display_name,
            "construction_year": self.construction_year,
            "building_typology": self.building_typology,
            "current_year": self.current_year,
            "envelope_u_values": self.envelope_u_values,
            "construction_set": self.construction_set.to_dict(),
            "renovation_log": [e.to_dict() for e in self.renovation_log],
        }

    def to_dict(self) -> dict:
        """Simplified dict for JSON export (backwards-compatible with NewSchema)."""
        return {
            "name": self.archetype_id,
            "age": self.construction_year,
            "total_elements": self.total_elements,
            "elements": [
                {"element_name": elem.name, "element_type": role.value}
                for role, elem in self.construction_set.elements.items()
            ],
        }

    def plot(self, **kwargs):
        """Draw architectural section drawings for all elements.

        Keyword arguments are forwarded to
        ``epsm_data.reporting.section_drawing.plot_sections``.
        """
        from epsm_data.reporting.section_drawing import plot_sections

        return plot_sections(self, **kwargs)


def build_construction_set(
    elements: dict[BuildingElement, Element | WindowElement],
    construction_year: int,
) -> ConstructionSet:
    """Convenience factory for the initial construction set."""
    return ConstructionSet(
        version_id=uuid4(),
        valid_from_year=construction_year,
        elements=elements,
    )
