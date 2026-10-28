"""Reusable archetypes composed from physical and operating definitions.

Catalogue entries and custom authoring use the same immutable hierarchy. An
archetype contains no geometry, calendar expansion or engine-specific model;
EPSM and Core apply its supplied definitions to a configured Building.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from uuid import UUID, uuid4

from ..profiles import HVACTemplate, OperatingProfile
from .editing import Editable
from .element import Element, WindowElement
from .enums import BuildingElement
from .envelope import EnvelopePerformance, _text_tuple


class _Roles(dict):
    """Element roles keyed by ``BuildingElement``; lookups also accept the role name."""

    @staticmethod
    def _role(key):
        try:
            return BuildingElement(key)
        except ValueError:
            raise KeyError(key) from None

    def __getitem__(self, key):
        return super().__getitem__(self._role(key))

    def __contains__(self, key):
        try:
            return super().__contains__(self._role(key))
        except KeyError:
            return False

    def get(self, key, default=None):
        return self[key] if key in self else default


@dataclass(frozen=True)
class ConstructionSet(Editable):
    """Construction snapshot at a recorded year.

    Parameters
    ----------
    version_id : UUID
        Snapshot identifier; preserved during serialization.
    valid_from_year : int
        Calendar year represented by this construction.
    elements : dict of BuildingElement to Element or WindowElement
        Role assignments, read-only. Look up a role by enum or by name:
        ``elements[BuildingElement.EXT_WALL]`` and ``elements["EXT_WALL"]`` are the same.
    """

    version_id: UUID = field(default_factory=uuid4)
    valid_from_year: int | None = None
    elements: Mapping[BuildingElement, Element | WindowElement] = field(default_factory=dict)

    def __post_init__(self):
        elements = {BuildingElement(role): element for role, element in self.elements.items()}
        for role, element in elements.items():
            if not isinstance(element, (Element, WindowElement)) or element.application != role:
                raise ValueError("Element application must match its construction role")
        object.__setattr__(self, "elements", MappingProxyType(_Roles(elements)))
        object.__setattr__(self, "version_id", UUID(str(self.version_id)))
        if self.valid_from_year is not None and (
            isinstance(self.valid_from_year, bool)
            or not isinstance(self.valid_from_year, int)
            or self.valid_from_year < 1
        ):
            raise ValueError("valid_from_year must be a positive year or None")

    def __deepcopy__(self, memo):
        # Every child is frozen and collections are normalized on construction.
        return self

    def with_element(self, role, element):
        """Assign a role in a new construction; validate the complete replacement."""
        return self.with_changes(
            version_id=uuid4(), elements={**self.elements, BuildingElement(role): element}
        )

    def to_dict(self) -> dict:
        """Return the snapshot or intervention record as plain data.

        Returns
        -------
        dict
            JSON-compatible values. Referenced objects remain named links;
            use archetype_to_dict for the complete resolved hierarchy.
        """
        return {
            "version_id": str(self.version_id),
            "valid_from_year": self.valid_from_year,
            "elements": {role.value: elem.to_dict() for role, elem in self.elements.items()},
        }


@dataclass(frozen=True)
class RenovationEvent(Editable):
    """Record an already-resolved renovation.

    Parameters
    ----------
    measure_id : str
        Caller-owned catalogue identity.
    applied_year : int
        Calendar year of the recorded intervention.
    trigger : str
        Caller-provided explanation; no policy is executed.
    removed_components, added_components : tuple of str
        Component names involved in the intervention.
    construction_set_before, construction_set_after : UUID
        Linked snapshot identities.
    cost_sek : float, optional
        Total cost in SEK; None means unknown.
    embodied_carbon_delta : float, optional
        Total intervention carbon delta in kg CO2e; None means unknown.
    """

    measure_id: str  # catalog key, e.g. "ventilation.install_ftx"
    applied_year: int
    trigger: str  # "end_of_life" | "policy" | "piggyback" | "user"
    removed_components: tuple[str, ...]  # component names removed
    added_components: tuple[str, ...]  # component names added
    construction_set_before: UUID
    construction_set_after: UUID
    cost_sek: float | None = None
    embodied_carbon_delta: float | None = None

    def __post_init__(self):
        object.__setattr__(self, "removed_components", tuple(self.removed_components))
        object.__setattr__(self, "added_components", tuple(self.added_components))

    def to_dict(self) -> dict:
        """Return the snapshot or intervention record as plain data.

        Returns
        -------
        dict
            JSON-compatible values. Referenced objects remain named links;
            use archetype_to_dict for the complete resolved hierarchy.
        """
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


@dataclass(frozen=True, repr=False)
class BuildingArchetype(Editable):
    """Reusable archetype identity, physical composition, and recorded changes.

    Parameters
    ----------
    archetype_id, display_name : str
        Stable caller-assigned identity and display label.
    construction_year : int or None
        Optional reference calendar year; unknown remains None.
    building_typology : str
        Caller classification, for example "multi_family".
    construction_set : ConstructionSet or None
        Current physical role assignments; partial and empty authoring is valid.
    operating_profile, hvac_template, envelope_performance : optional
        Independently reusable definitions. Omission never selects defaults.
    source_references, notes : tuple of str
        Explicit provenance and modelling assumptions, retained in exchange.
    renovation_log : tuple of RenovationEvent, optional
        Already-resolved interventions, in recorded order.

    Notes
    -----
    This object contains neither geometry nor scenario execution. Use
    build_archetype for a recipe-based constructor and archetype_to_dict for
    lossless exchange of materials, constructions, and IDs.
    """

    archetype_id: str  # e.g. "CMF_1950"
    display_name: str
    construction_year: int | None = None
    building_typology: str = "unknown"
    construction_set: ConstructionSet | None = None
    renovation_log: tuple[RenovationEvent, ...] = ()
    operating_profile: OperatingProfile | None = None
    hvac_template: HVACTemplate | None = None
    envelope_performance: EnvelopePerformance | None = None
    source_references: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("archetype_id", "display_name", "building_typology"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonempty text")
        year = self.construction_year
        if year is not None and (isinstance(year, bool) or not isinstance(year, int) or year < 1):
            raise ValueError("construction_year must be a positive year or None")
        for name, expected in (
            ("construction_set", ConstructionSet),
            ("operating_profile", OperatingProfile),
            ("hvac_template", HVACTemplate),
            ("envelope_performance", EnvelopePerformance),
        ):
            value = getattr(self, name)
            if value is not None and not isinstance(value, expected):
                raise ValueError(f"{name} must be {expected.__name__} or None")
        for name in ("source_references", "notes"):
            object.__setattr__(self, name, _text_tuple(getattr(self, name), name))
        events = tuple(self.renovation_log)
        if any(not isinstance(event, RenovationEvent) for event in events):
            raise ValueError("renovation_log must contain RenovationEvent records")
        object.__setattr__(self, "renovation_log", events)

    @property
    def missing_sections(self) -> tuple[str, ...]:
        """Absent definition sections; this is not a simulation-readiness check."""
        names = ("construction_set", "operating_profile", "hvac_template", "envelope_performance")
        return tuple(
            name
            for name in names
            if getattr(self, name) is None
            or (name == "construction_set" and not self.construction_set.elements)
        )

    def summary(self) -> dict:
        """Inspect loaded identities, sources, assumptions and definition completeness."""
        return {
            "archetype_id": self.archetype_id,
            "display_name": self.display_name,
            "construction_year": self.construction_year,
            "building_typology": self.building_typology,
            "total_elements": self.total_elements,
            "missing_sections": self.missing_sections,
            "operating_profile": self.operating_profile.to_dict()
            if self.operating_profile
            else None,
            "hvac_template": self.hvac_template.to_dict() if self.hvac_template else None,
            "envelope_performance": self.envelope_performance.to_dict()
            if self.envelope_performance
            else None,
            "source_references": self.source_references,
            "notes": self.notes,
        }

    def __repr__(self):
        label = repr(self.archetype_id)
        if len(label) > 65:
            label = repr(self.archetype_id[:8] + "…")
        if len(label) > 65:
            label = "'…'"
        return f"BuildingArchetype(id={label}, elements={self.total_elements}, missing={len(self.missing_sections)})"

    __str__ = __repr__

    @property
    def current_year(self) -> int | None:
        """Latest year reflected in the archetype state."""
        if self.renovation_log:
            return max(e.applied_year for e in self.renovation_log)
        return self.construction_year

    def with_renovation(
        self,
        event: RenovationEvent,
        new_construction_set: ConstructionSet,
    ) -> BuildingArchetype:
        """Record a supplied snapshot and event in a new archetype.

        Parameters
        ----------
        event : RenovationEvent
            Record of an intervention already resolved by the caller.
        new_construction_set : ConstructionSet
            Resulting composition; no physical measure is applied here.

        Returns
        -------
        BuildingArchetype
            New record with the appended event. The original is unchanged.
        """
        return self.with_changes(
            construction_set=new_construction_set,
            renovation_log=self.renovation_log + (event,),
        )

    @property
    def envelope_u_values(self) -> dict[str, float]:
        """Nominal U-values in W/(m² K), keyed by role name (``"EXT_WALL"``, ``"WINDOW"`` …).

        Exterior wall variants (LOW, MEDIUM, HIGH) are averaged under ``"EXT_WALL"``.
        Ground and basement values are the material layers only, without the soil; the
        catalogue's ``nominal_metadata(...)["boundary_details"]`` explains each boundary.
        """
        result: dict[str, float] = {}
        wall_values: list[float] = []

        if self.construction_set is None:
            return result

        for role, elem in self.construction_set.elements.items():
            if role == BuildingElement.WINDOW:
                result["WINDOW"] = elem.u_value
            elif role.is_ext_wall:
                wall_values.append(elem.u_value)
            else:
                result[role.value] = elem.u_value

        if wall_values:
            result["EXT_WALL"] = sum(wall_values) / len(wall_values)

        return result

    @property
    def window(self) -> WindowElement | None:
        """Shortcut to the window element, if present."""
        elem = (
            self.construction_set.elements.get(BuildingElement.WINDOW)
            if self.construction_set
            else None
        )
        return elem if isinstance(elem, WindowElement) else None

    @property
    def total_elements(self) -> int:
        """Number of assigned element roles, including windows."""
        return len(self.construction_set.elements) if self.construction_set else 0

    def plot(self, **kwargs):
        """Draw architectural section drawings for all elements.

        Keyword arguments are forwarded to
        ``epsm_data.plotting.plot_sections``.
        """
        from epsm_data.plotting import plot_sections

        return plot_sections(self, **kwargs)


def build_construction_set(
    elements: dict[BuildingElement, Element | WindowElement],
    construction_year: int,
) -> ConstructionSet:
    """Assign a new UUID to a construction snapshot.

    Parameters
    ----------
    elements : dict
        BuildingElement keys mapped to resolved elements.
    construction_year : int
        Calendar year represented by the snapshot.

    Returns
    -------
    ConstructionSet
        Snapshot with a fresh version_id.
    """
    return ConstructionSet(
        version_id=uuid4(),
        valid_from_year=construction_year,
        elements=elements,
    )


# Public name for the existing construction archetype wrapper.
Archetype = BuildingArchetype
