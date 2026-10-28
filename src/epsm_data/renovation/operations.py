"""Executable construction changes expressed with the shared physical types.

Operations transform an immutable construction. Core selects actual building
elements, applies ordered stages and records material occurrences and quantities.
No calendar, simulation, cost calculation or catalogue loading occurs here.
"""

from dataclasses import dataclass, replace

from ..catalogue.serialization import _component, _encode, element_from_dict
from ..domain import BuildingElement, Component, ConstructionSet, Element, WindowElement
from ..domain.editing import Editable
from ..profiles.operating import HVACTemplate


@dataclass(frozen=True)
class ConstructionOperation(Editable):
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
        return _encode(self)

    @classmethod
    def from_dict(cls, data):
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
        return {"action": self.action, "template": self.template.to_dict()}

    @classmethod
    def from_dict(cls, data):
        return cls(data["action"], HVACTemplate.from_dict(data["template"]))
