from typing import List, Tuple
from ClassDefinitions.Materials import Material
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


class Layer:
    """
    Represents a construction layer — either homogeneous (one material)
    or composite (multiple materials sharing the same thickness).
    """

    def __init__(
        self,
        thickness: float,  # m
        materials: List[Tuple[Material, float | None]],
        name: str = "",
        archetype: str = ""
    ):
        self.name = name
        self.thickness = thickness
        self.materials = materials
        self.archetype = archetype

        # Will be injected by Component if needed
        self.shearing_layer = None  # placeholder for Component

    # Validation (returns warnings)
    def validate(self) -> List[str]:
        warnings = []

        # Thickness
        if self.thickness is None or self.thickness <= 0:
            warnings.append("Layer thickness must be a positive number.")

        # Materials
        if not self.materials:
            warnings.append("Layer must contain at least one material.")


        fractions = []
        for mat, fraction in self.materials:
            if mat is None:
                warnings.append("Material cannot be None.")
                continue

            if mat.conductivity is None or mat.conductivity <= 0:
                warnings.append(f"Material '{getattr(mat, 'name', 'Unknown')}' has invalid conductivity.")

            if fraction is None:
                warnings.append(f"Missing area fraction for material '{getattr(mat, 'name', 'Unknown')}'.")
            elif fraction <= 0:
                warnings.append(f"Area fraction for material '{getattr(mat, 'name', 'Unknown')}' must be positive.")

            if fraction is not None:
                fractions.append(fraction)

        # Area fractions
        if len(fractions) > 1 and abs(sum(fractions) - 1.0) > 1e-6:
            warnings.append("Material area fractions must sum to 1.")

        return warnings

    # Calculations
    def calculate_r_value(self) -> float:
        """
        Calculate effective R-value [m²·K/W] using the average
        of the R-λ and R-U methods.
        Raises if validation fails.
        """
        warnings = self.validate()
        if warnings:
            raise ValueError(f"Cannot calculate R-value due to: {warnings}")

        d = self.thickness
        lambdas = [mat.conductivity for mat, _ in self.materials]
        fractions = [fraction for _, fraction in self.materials]

        R_lambda = d / sum(f * lam for f, lam in zip(fractions, lambdas))
        u_sum = sum(f * lam / d for f, lam in zip(fractions, lambdas))
        R_U = 1 / u_sum

        return 0.5 * (R_lambda + R_U)

    @property
    def r_value(self) -> float:
        """Dynamic R-value (always recalculated)."""
        return self.calculate_r_value()

    # Diagram
    def plot(self, figsize=(4, 6)) -> None:
        """
        Plot a vertical stack of materials in the layer.
        Pure presentation: does not mutate state.
        """
        warnings = self.validate()
        if warnings:
            print(f"[Layer WARNING] {self.name}: {warnings}")

        fig, ax = plt.subplots(figsize=figsize)
        y_start = 0.0
        total_height = 1.0

        d = self.thickness
        lambdas = [mat.conductivity for mat, _ in self.materials]
        fractions = [fraction for _, fraction in self.materials]
        u_sum = sum(f * lam / d for f, lam in zip(fractions, lambdas))
        R_U_total = 1 / u_sum if u_sum != 0 else 0

        for (mat, fraction) in self.materials:
            height = fraction * total_height if fraction is not None else 0
            R_lambda_contrib = fraction * d / mat.conductivity if fraction else 0
            R_U_contrib = R_U_total * fraction if fraction else 0
            R_avg_contrib = 0.5 * (R_lambda_contrib + R_U_contrib)

            rect = Rectangle((0, y_start), 1, height, edgecolor="black", facecolor="lightgray")
            ax.add_patch(rect)
            ax.text(0.5, y_start + height / 2,
                    f"{mat.name}\nR={R_avg_contrib:.3f} m²·K/W",
                    ha="center", va="center", fontsize=10)
            y_start += height

        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title(f"Layer: {self.name}\nThickness = {self.thickness} m | R_total = {self.r_value:.3f} m²·K/W",
                     pad=12)
        plt.show()

    # Serialization
    def to_dict(self) -> dict:
        """Serialize layer data for export."""
        return {
            "name": self.name,
            "thickness": self.thickness,
            "r_value": self.r_value,
            "archetype:": self.archetype,
            "materials": [
                {"name": mat.name, "fraction": fraction}
                for mat, fraction in self.materials
            ],
        }
