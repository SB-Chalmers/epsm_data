from typing import List
from EPSM_Enums import ShearingLayer
from ClassDefinitions.Layers import Layer
from datetime import datetime


class Component:
    """
    Represents a construction component (e.g., wall assembly)
    consisting of multiple layers and surface resistances.
    Each layer has its own shearing_layer.
    """

    #DEFAULT_RSI = 0.13  # typical internal surface resistance [m²·K/W]
    #DEFAULT_RSE = 0.04  # typical external surface resistance [m²·K/W]

    def __init__(
        self,
        name: str,
        archetype: str,
        layers: List[Layer],
        shearing_layer: ShearingLayer,
        year_installed: int = None,
        #rsi: float = None,
        #rse: float = None,
    ):
        if not layers:
            raise ValueError("Component must have at least one layer.")
        if not all(isinstance(layer, Layer) for layer in layers):
            raise TypeError("All items in 'layers' must be instances of Layer.")

        self.name = name
        self.archetype = archetype
        self.layers = layers

        # Assign default surface resistances if not provided
        #self.rsi = rsi if rsi is not None else self.DEFAULT_RSI
        #self.rse = rse if rse is not None else self.DEFAULT_RSE

        # Propagate shearing_layer to each layer
        for layer in self.layers:
            layer.shearing_layer = shearing_layer

        self.year_installed = year_installed

    # Validation
    def validate(self) -> list[str]:
        warnings = []

        # Check that layers exist
        if not self.layers:
            warnings.append("Component has no layers.")

        for i, layer in enumerate(self.layers, start=1):
            # Check if layer is proper Layer instance
            if not isinstance(layer, Layer):
                warnings.append(f"Layer {i} is not a valid Layer object.")
                continue

            # Call layer validation
            layer_warnings = layer.validate()
            if layer_warnings:
                for w in layer_warnings:
                    warnings.append(f"Layer '{layer.name}': {w}")

            # Check shearing_layer
            if layer.shearing_layer is None:
                warnings.append(f"Layer '{layer.name}' has no shearing_layer assigned.")

            # Optional: check extreme R-values
            r_val = getattr(layer, "r_value", None)
            if r_val is not None and r_val <= 0:
                warnings.append(f"Layer '{layer.name}' has non-positive R-value: {r_val}")

        # Check component total R-value sanity
        r_total = getattr(self, "r_value_total", None)
        if r_total is not None and r_total <= 0:
            warnings.append(f"Component '{self.name}' has non-positive total R-value: {r_total}")

        return warnings


    def calculate_r_value(self) -> float:
        """
        Calculate total R-value including surface resistances.
        Handles None values for layers.
        """
        return sum(layer.r_value or 0 for layer in self.layers)

    @property
    def r_value_total(self) -> float:
        """Dynamic total R-value including all layers and surface resistances."""
        return self.calculate_r_value()

    """@property
    def u_value(self) -> float | None:
        r_total = self.r_value_total
        if r_total <= 0:
            return None
        return 1 / r_total"""

    @property
    def age(self) -> int | None:
        """Calculate the age of the component."""
        if self.year_installed is None:
            return None
        current_year = datetime.now().year
        if self.year_installed > current_year:
            return None  # invalid future year
        return current_year - self.year_installed


    def print_info(self):
        print(f"Component: {self.name}")
        print(f"{'Layer':<20}{'R-value (m²·K/W)':<20}{'Shearing Layer':<15}")
        print("-" * 55)
        for i, layer in enumerate(self.layers, start=1):
            layer_name = getattr(layer, "name", f"Layer {i}")
            shearing = getattr(layer, "shearing_layer", None)
            shearing_value = shearing.value if shearing else "Unknown"
            r_val = layer.r_value if layer.r_value is not None else 0
            print(f"{layer_name:<20}{r_val:<20.2f}{shearing_value:<15}")

        print("-" * 55)
        print(f"{'Total R-value:':<20}{self.r_value_total:.2f} m²·K/W")
        #u_val = self.u_value
        #print(f"{'U-value:':<20}{u_val:.3f} W/m²·K" if u_val is not None else f"{'U-value:':<20}Error")
        print(f"{'Age:':<20}{self.age if self.age is not None else 'Unknown'} years\n")


    def to_dict(self):
        """Serialize for export, adding layer_index and shearing_layer per layer."""
        layers_with_index = []
        for idx, layer in enumerate(self.layers, start=1):
            layer_dict = layer.to_dict()
            layer_dict["layer_index"] = idx
            layer_dict["shearing_layer"] = layer.shearing_layer.value if layer.shearing_layer else None
            layers_with_index.append(layer_dict)

        return {
            "name": self.name,
            "archetype": self.archetype,
            #"rsi": self.rsi,
            #"rse": self.rse,
            "r_value_total": self.r_value_total,
            "age": self.age,
            "layers": layers_with_index,
        }
