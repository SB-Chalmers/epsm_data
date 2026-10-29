"""Executable construction changes expressed with the shared physical types.

Operations transform an immutable construction. Core selects actual building
elements, applies ordered stages and records material occurrences and quantities.
No calendar, simulation, cost calculation or catalogue loading occurs here.
"""

from dataclasses import dataclass, replace

from ..catalogue.serialization import _component, _encode, element_from_dict
from ..domain import BuildingElement, Component, ConstructionSet, Element, WindowElement
from ..domain.editing import Editable
from ..profiles import HVACTemplate


@dataclass(frozen=True)
class ConstructionOperation(Editable):
    """Declarative change to one element role's construction; Core applies it.

    ``action`` is one of:

    - ``add_component``: insert ``component`` at ``position`` (outside to inside);
    - ``replace_component``: replace the component named ``target_component``;
    - ``remove_component``: remove the component named ``target_component``;
    - ``replace_element``: replace the whole ``element``.

    An incoming component or element must match ``role``.
    """

    action: str
    role: BuildingElement
    component: Component | None = None
    element: Element | WindowElement | None = None
    target_component: str | None = None
    position: int | None = None

    def __post_init__(self):
        object.__setattr__(self, "role", BuildingElement(self.role))
        if self.action not in {"add_component", "replace_component", "remove_component", "replace_element"}:
            raise ValueError(f"Unknown construction action: {self.action}")
        if self.action in {"add_component", "replace_component"}:
            if not isinstance(self.component, Component) or self.component.application != self.role:
                raise ValueError("The incoming component must match the operation role")
        elif self.component is not None:
            raise ValueError("This action does not accept an incoming component")
        if self.action == "replace_element":
            if not isinstance(self.element, (Element, WindowElement)) or self.element.application != self.role:
                raise ValueError("The replacement element must match the operation role")
        elif self.element is not None:
            raise ValueError("Only replace_element accepts an element")
        if self.action in {"replace_component", "remove_component"}:
            if not isinstance(self.target_component, str) or not self.target_component.strip():
                raise ValueError("An explicit component name is required")
        elif self.target_component is not None:
            raise ValueError("This action does not accept a component selector")
        if self.action == "add_component":
            if isinstance(self.position, bool) or not isinstance(self.position, int) or self.position < 0:
                raise ValueError("Adding a component requires its outside-to-inside position")
        elif self.position is not None:
            raise ValueError("Only add_component accepts a position")

    def apply(self, construction: ConstructionSet) -> ConstructionSet:
        """Return the changed construction, rejecting missing or ambiguous targets."""
        if self.role not in construction.elements:
            raise ValueError(f"Construction has no {self.role.value} element")
        if self.action == "replace_element":
            return construction.with_element(self.role, self.element)
        old = construction.elements[self.role]
        if not isinstance(old, Element):
            raise ValueError("Component operations require a layered element")
        components = list(old.components)
        if self.action == "add_component":
            if self.position > len(components):
                raise ValueError("Component position exceeds the existing stack")
            components.insert(self.position, self.component)
        else:
            matches = [i for i, c in enumerate(components) if c.name == self.target_component]
            if len(matches) != 1:
                raise ValueError(f"Expected one component named {self.target_component!r}")
            if self.action == "replace_component":
                components[matches[0]] = self.component
            else:
                components.pop(matches[0])
        return construction.with_element(self.role, replace(old, components=tuple(components)))

    def to_dict(self):
        """Return a JSON-compatible mapping."""
        return _encode(self)

    @classmethod
    def from_dict(cls, data):
        """Rebuild an operation from ``to_dict`` output."""
        values = dict(data)
        if values.get("component") is not None:
            values["component"] = _component(values["component"])
        if values.get("element") is not None:
            values["element"] = element_from_dict(values["element"])
        return cls(**values)


@dataclass(frozen=True)
class SystemOperation(Editable):
    """Declarative HVAC replacement; Core applies it to a physical Building."""

    action: str
    template: HVACTemplate

    def __post_init__(self):
        if self.action != "replace_hvac" or not isinstance(self.template, HVACTemplate):
            raise ValueError("SystemOperation requires replace_hvac and an HVACTemplate")

    def to_dict(self):
        """Return a JSON-compatible mapping."""
        return {"action": self.action, "template": self.template.to_dict()}

    @classmethod
    def from_dict(cls, data):
        """Rebuild an operation from ``to_dict`` output."""
        return cls(data["action"], HVACTemplate.from_dict(data["template"]))


@dataclass(frozen=True)
class AirtightnessOperation(Editable):
    """Declarative reduction of envelope infiltration; Core applies it to a Building.

    ``fraction`` is the share of the current infiltration removed, in (0, 1).
    """

    action: str
    fraction: float

    def __post_init__(self):
        if self.action != "reduce_infiltration":
            raise ValueError("AirtightnessOperation requires reduce_infiltration")
        if (isinstance(self.fraction, bool) or not isinstance(self.fraction, (int, float))
                or not 0 < self.fraction < 1):
            raise ValueError("Infiltration reduction must be a fraction in (0, 1)")

    def to_dict(self):
        return {"action": self.action, "fraction": self.fraction}

    @classmethod
    def from_dict(cls, data):
        return cls(data["action"], data["fraction"])


@dataclass(frozen=True)
class PVOperation(Editable):
    """Declarative addition of one PV array; Core sizes it and appends it to a Building."""

    action: str
    dc_capacity_kw: float
    tilt_deg: float
    azimuth_deg: float
    system_losses_pct: float

    def __post_init__(self):
        if self.action != "add_pv":
            raise ValueError("PVOperation requires add_pv")
        if not self.dc_capacity_kw > 0 or not 0 <= self.tilt_deg <= 90 \
                or not 0 <= self.azimuth_deg < 360 or not 0 <= self.system_losses_pct < 100:
            raise ValueError("PV capacity, tilt, azimuth or losses are out of range")

    def to_dict(self):
        return {"action": self.action, "dc_capacity_kw": self.dc_capacity_kw,
                "tilt_deg": self.tilt_deg, "azimuth_deg": self.azimuth_deg,
                "system_losses_pct": self.system_losses_pct}

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@dataclass(frozen=True)
class DHWOperation(Editable):
    """Declarative reduction of domestic hot-water use; Core applies it to a Building."""

    action: str
    fraction: float

    def __post_init__(self):
        if self.action != "reduce_dhw":
            raise ValueError("DHWOperation requires reduce_dhw")
        if (isinstance(self.fraction, bool) or not isinstance(self.fraction, (int, float))
                or not 0 < self.fraction < 1):
            raise ValueError("DHW reduction must be a fraction in (0, 1)")

    def to_dict(self):
        return {"action": self.action, "fraction": self.fraction}

    @classmethod
    def from_dict(cls, data):
        return cls(data["action"], data["fraction"])
