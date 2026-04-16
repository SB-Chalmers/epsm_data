"""Layer thermal calculations placeholder.

Expected contents:
- Homogeneous layer resistance. - Y
- Composite layer transmittance using area/path methods. - Y
- Input assumptions and audit metadata.
"""

from epsm_data.domain.layer import Layer

def compute_layer_r_value(layer: "Layer") -> float:
    """Compute the effective thermal resistance of a layer [m²·K/W].

    For single-material layers, applies the lambda method directly:
        R = d / λ

    For composite layers (parallel heat flow paths), uses the average of
    the lambda method and the U-value method, per Persson (2018) sections
    8.1 and 9.2.3:

        Lambda method:  R = d / lambda_avg    where lambda_avg = sum(lambda_i * f_i)
        U-value method: R = 1 / sum(lambda_i/d * f_i)
        Result:         R = 0.5 * (R_lambda + R_u)
    

    Args:
        layer: Layer instance containing thickness, materials, area fractions.

    Returns:
        Effective R-value in m²·K/W.

    Raises:
        ValueError: If average conductivity is zero or negative.

    References:
        Persson, B. P.-Å. (2018). Tillämpad byggnadsfysik. Studentlitteratur.
        Chalmers lecture material, course 9012.
    """
    d = layer.thickness

    if len(layer.materials) == 1:
        mat, _, _ = layer.materials[0]
        if mat.conductivity <= 0:
            raise ValueError(
            f"Invalid average conductivity ({mat.conductivity}) in layer {layer.name}"
        )
        return d / mat.conductivity

    avg_lambda = sum(mat.conductivity * frac for mat, frac, _ in layer.materials)
    if avg_lambda <= 0:
        raise ValueError(
            f"Invalid average conductivity ({avg_lambda}) in layer {layer.name}"
        )

    r_lambda_method = d / avg_lambda
    total_u = sum((mat.conductivity / d) * frac for mat, frac, _ in layer.materials)
    r_u_method = 1 / total_u if total_u > 0 else 0.0

    return 0.5 * (r_lambda_method + r_u_method)
