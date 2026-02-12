from typing import List
from ClassDefinitions.Components import Component
from EPSM_Enums import ShearingLayer

# NOT IN USE - READING ELEMENTS AS DICTS IN EXTRACTINGMATERIALS/ExtractElements.py

class Element:
    """
    Represents a construction element (e.g., wall, floor, roof)
    consisting of multiple components.
    Surface resistances (rsi/rse) are applied at the element level.
    """

    DEFAULT_RSI = 0.13  # internal surface resistance
    DEFAULT_RSE = 0.04  # external surface resistance

    def __init__(self, name: str, archetype: str, components: List[Component], rsi: float = None, rse: float = None):
        if not name or not isinstance(name, str):
            raise ValueError("Element must have a non-empty string 'name'.")
        if not archetype or not isinstance(archetype, str):
            raise ValueError("Element must have a non-empty string 'archetype'.")
        if not components:
            raise ValueError("Element must have at least one component.")
        if not all(isinstance(comp, Component) for comp in components):
            raise TypeError("All items in 'components' must be instances of Component.")

        self.name = name
        self.archetype = archetype
        self.components = components
        self.rsi = rsi if rsi is not None else self.DEFAULT_RSI
        self.rse = rse if rse is not None else self.DEFAULT_RSE
        
        # Validate R-value immediately after all attributes are set
        if self.r_value_total <= 0:
            raise ValueError(
                f"Element '{self.name}' has invalid total R-value ({self.r_value_total:.3f}). "
                f"Check component thermal properties and surface resistances."
            )

    def validate(self) -> list[str]:
        """Run validation checks on the element and its components."""
        warnings = []

        # Check element-level properties
        if not isinstance(self.rsi, (int, float)) or self.rsi <= 0:
            warnings.append(f"Invalid RSI value: {self.rsi}")
        if not isinstance(self.rse, (int, float)) or self.rse <= 0:
            warnings.append(f"Invalid RSE value: {self.rse}")

        # Validate components
        for i, comp in enumerate(self.components, start=1):
            if not isinstance(comp, Component):
                warnings.append(f"Item {i} in components is not a valid Component.")
                continue

            # Check component R-value
            if comp.r_value_total <= 0:
                warnings.append(f"Component '{comp.name}' has non-positive R-value: {comp.r_value_total}")

            # Include component-level warnings
            comp_warnings = comp.validate()
            for w in comp_warnings:
                warnings.append(f"Component '{comp.name}': {w}")

        # Check element R-value sanity
        if self.r_value_total <= 0:
            warnings.append(f"Element '{self.name}' has non-positive total R-value: {self.r_value_total}")

        return warnings

    @property
    def r_value_total(self) -> float:
        """Total R-value including element-level surface resistances."""
        total_r = sum(comp.r_value_total for comp in self.components)
        return self.rsi + total_r + self.rse

    @property
    def u_value_total(self) -> float:
        """Overall U-value [W/m²·K] of the element."""
        r_total = self.r_value_total
        if r_total <= 0:
            raise ValueError(
                f"Invalid state: Element '{self.name}' has R-value ≤ 0"
            )
        return round(1 / r_total, 5)

    @property
    def age(self) -> int | None:
        """Element age based on the oldest component."""
        component_ages = [comp.age for comp in self.components if comp.age is not None]
        return max(component_ages) if component_ages else None

    def print_info(self):
        print(f"Element: {self.name} (Archetype: {self.archetype})")
        print(f"{'Component':<25}{'R-value (m²·K/W)':<20}{'Shearing Layer':<15}")
        print("-" * 60)
        for comp in self.components:
            shearing = getattr(comp.layers[0], "shearing_layer", None)
            shearing_val = shearing.value if shearing else "Unknown"
            print(f"{comp.name:<25}{comp.r_value_total:<20.3f}{shearing_val:<15}")
        print("-" * 60)
        print(f"{'Element R-value total:':<25}{self.r_value_total:.3f} m²·K/W")
        print(f"{'Element U-value total:':<25}{self.u_value_total:.3f} W/m²·K")
        print(f"{'Age:':<25}{self.age if self.age is not None else 'Unknown'} years\n")

    def to_dict(self):
        return {
            "name": self.name,
            "archetype": self.archetype,
            "rsi": self.rsi,
            "rse": self.rse,
            "r_value_total": self.r_value_total,
            "u_value_total": self.u_value_total,
            "age": self.age,
            "components": [comp.to_dict() for comp in self.components]
        }