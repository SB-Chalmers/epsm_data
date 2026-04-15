"""Reference standards and validation tolerances.

Provides TABULA reference lookup and tolerance-band validation for
computed U-values against reference data.
"""

from __future__ import annotations

from epsm_data.domain.element import TABULA_CMF, Element
from epsm_data.domain.enums import BuildingElement

# Re-export for convenience
REFERENCE_U_VALUES = TABULA_CMF

# Default tolerance for TABULA validation (±20%)
DEFAULT_TOLERANCE = 0.2


def get_reference_u_value(
    archetype_key: str,
    element_type: str,
) -> float | None:
    """Look up a TABULA reference U-value.

    Parameters
    ----------
    archetype_key : e.g. "CMF_1950"
    element_type  : e.g. "wall", "roof", "floor", "window", "basement_wall"
    """
    entry = REFERENCE_U_VALUES.get(archetype_key)
    if entry is None:
        return None
    return entry.get(element_type)


def validate_against_reference(
    element: Element,
    tolerance: float = DEFAULT_TOLERANCE,
) -> str | None:
    """Check element U-value against TABULA reference.

    Returns a warning string if outside the tolerance band, else None.
    """
    return element.check_tabula(REFERENCE_U_VALUES, threshold=tolerance)
