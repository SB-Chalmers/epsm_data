"""Compare calculated U-values with explicitly supplied reference values."""

from math import isfinite

DEFAULT_TOLERANCE = 0.2


def validate_against_reference(
    u_value: float, reference_u_value: float | None, *, tolerance: float = DEFAULT_TOLERANCE
) -> str | None:
    """Compare a calculated U-value to a caller-selected reference.

    Parameters
    ----------
    u_value : float
        Calculated thermal transmittance in W/(m² K).
    reference_u_value : float or None
        Reference in the same units. None means no comparison is requested.
    tolerance : float, optional
        Relative tolerance, default 0.2 (20 percent).

    Returns
    -------
    str or None
        Warning if outside the tolerance band, otherwise None.

    Raises
    ------
    ValueError
        Values are non-finite, non-positive, or tolerance is negative.
    """
    if not isfinite(u_value) or u_value <= 0:
        raise ValueError("U-value must be finite and positive")
    if not isfinite(tolerance) or tolerance < 0:
        raise ValueError("Tolerance must be finite and non-negative")
    if reference_u_value is None:
        return None
    if not isfinite(reference_u_value) or reference_u_value <= 0:
        raise ValueError("Reference U-value must be finite and positive")
    if abs(u_value - reference_u_value) > tolerance * reference_u_value:
        return (
            f"U-value {u_value:.4f} outside reference range "
            f"(+/-{tolerance * 100:.0f}%) of {reference_u_value}"
        )
    return None
