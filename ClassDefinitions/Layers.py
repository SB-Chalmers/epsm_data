from typing import List, Tuple, Union
from ClassDefinitions.Materials import Material, concrete, glass
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

#this needs to fixed for usability later on. #How do we calculate R-value for composite layers? And U-value? for element was there a specific formula? 
# Is the composite tactic uneccessary, better with two classes instead? and etc. # # R-Value check with Angela. 
# add a plot function plot a unit section, rectangles labels etc 
#  validate again.


class Layer:
    """
    Represents a construction layer — either homogeneous (one material)
    or composite (multiple materials sharing the same thickness).
    """

    def __init__(
        self,
        thickness: float,  # m
        materials: Union[Material, List[Tuple[Material, float]]],
    ):
        """
        Parameters
        ----------
        thickness : float
            Layer thickness in meters.

        materials : Material or list of (Material, fraction)
            - Single Material → homogeneous layer.
            - List of (Material, area_fraction) → composite layer.
        """
        self.thickness = thickness

        # Normalize to a list of tuples
        if isinstance(materials, list):
            self.materials = materials
        else:
            self.materials = [(materials, 1.0)]

        # Calculate effective R-value
        self.r_value = self.calculate_r_value()

    #Uses Lambda method and U-value method to calculate R-value --> average of the two
    def calculate_r_value(self) -> float:
        d = self.thickness

        lambdas = []
        fractions = []

        for mat, fraction in self.materials:
            if mat.conductivity <= 0:
                continue
            lambdas.append(mat.conductivity)
            fractions.append(fraction)

        if not lambdas:
            return None

        # 1) λ-value weighted method
        lambda_eq = sum(f * lam for f, lam in zip(fractions, lambdas))
        R_lambda = d / lambda_eq

        # 2) U-value (parallel) method
        # 1/R = Σ( f_i * λ_i / d )
        u_sum = sum(f * lam / d for f, lam in zip(fractions, lambdas))
        R_U = 1 / u_sum

        # combined R-value
        R_final = 0.5 * (R_lambda + R_U)

        return R_final

    def to_dict(self):
        """Return this layer as a dictionary for export or serialization."""
        return {
            "thickness": self.thickness,
            "r_value": self.r_value,
            "materials": [
                {
                    "name": mat.name,
                    "conductivity": mat.conductivity,
                    "fraction": fraction,
                }
                for mat, fraction in self.materials
            ],
        }
    
    
    def plot(self, figsize=(4, 6)):
        """
        Plot a vertical stack of the materials in the layer,
        showing each material's fraction and contribution to the total R-value.
        """
        fig, ax = plt.subplots(figsize=figsize)
        y_start = 0.0
        total_height = 1.0

        # Precompute λ- and U-based contributions for consistent R display
        total_R_lambda = self.thickness / sum(f * mat.conductivity for mat, f in self.materials)
        total_R_U = 1 / sum(f * mat.conductivity / self.thickness for mat, f in self.materials)
        total_R = 0.5 * (total_R_lambda + total_R_U)

        for mat, fraction in self.materials:
            height = fraction * total_height

            # Contribution fractions (proportional to λ and U)
            R_lambda_contrib = (fraction * self.thickness / mat.conductivity)
            R_U_contrib = 1 / (sum(f * mat_i.conductivity / self.thickness for mat_i, f in self.materials) ) * fraction
            R_avg_contrib = 0.5 * (R_lambda_contrib + R_U_contrib)

            rect = Rectangle((0, y_start), 1, height, edgecolor="black", facecolor="lightgray")
            ax.add_patch(rect)

            ax.text(
                0.5, y_start + height / 2,
                f"{mat.name}\nR_contrib={R_avg_contrib:.3f} m²K/W",
                ha="center", va="center", fontsize=10
            )

            y_start += height

        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_aspect("equal")
        ax.axis("off")
        plt.title(f"Layer Thickness = {self.thickness} m | R_total = {self.r_value:.3f} m²K/W", pad=15)
        plt.show()


# Examples
Concrete_Layer = Layer(
    thickness=0.2,
    materials=concrete
)

Franken_Layer = Layer(
    thickness=0.2,
    materials=[
        (concrete, 0.85),
        (glass, 0.15)
    ]
)

if __name__ == "__main__":
    Franken_Layer.plot()
