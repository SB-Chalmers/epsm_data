"""Reference standards placeholder.

Expected contents:
- TABULA and/or ISO reference lookups.
- Validation tolerance policies.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from epsm_data.domain.element import Elements


# Hardcoded Tabula CMF reference values, check if needed anywhere else (shouldn't)
TABULA_CMF = {
    "CMF_1940": {"roof": 0.36, "wall": 0.58, "window": 2.22, "floor": 0.32, "basement_wall": 0.70 },#...1960
    "CMF_1950": {"roof": 0.36, "wall": 0.58, "window": 2.22, "floor": 0.32, "basement_wall": 0.70 },#...1960
    "CMF_1960": {"roof": 0.20, "wall": 0.41, "window": 2.22, "floor": 0.26, "basement_wall": 0.70},# 1961 - 1975
    "CMF_1970": {"roof": 0.20, "wall": 0.41, "window": 2.22, "floor": 0.26, "basement_wall": 0.70},# 1961 - 1975
    "CMF_1980": {"roof": 0.17, "wall": 0.33, "window": 2.04, "floor": 0.27, "basement_wall": 0.70},# 1976 - 1985
    "CMF_1990": {"roof": 0.15, "wall": 0.22, "window": 1.80, "floor": 0.24, "basement_wall": 0.70},# 1986 - 1995
}

def match_tabula(element: Elements, tabula_data: dict) -> tuple[str, str] | None:
    """Resolve archetype and element type keys for a Tabula lookup.

    Matches the element name against archetype keys in tabula_data,
    and maps the element application to a Tabula element type string
    using the element's TABULA_TYPE_MAP.

    Args:
        element: Elements instance to match against the reference data.
        tabula_data: Reference dict keyed by archetype (e.g. TABULA_CMF).

    Returns:
        Tuple of (matched_archetype, matched_type) if a match is found,
        or None if the element name or application has no match.
    """
    name_upper = element.name.upper()
    matched_archetype = next(
        (k for k in tabula_data if k.upper() in name_upper), None
    )
    if matched_archetype is None:
        return None
    matched_type = element.TABULA_TYPE_MAP.get(element.application)
    if matched_type is None:
        return None
    return matched_archetype, matched_type

def tabula_u_value(element: Elements) -> float | None:
    """Look up the Tabula reference U-value for an element.

    Args:
        element: Elements instance to look up.

    Returns:
        Reference U-value in W/m2·K, or None if no match in TABULA_CMF.
    """
    match = match_tabula(element, TABULA_CMF)
    if match is None:
        return None
    matched_archetype, matched_type = match
    return TABULA_CMF[matched_archetype][matched_type]

def check_tabula(element: Elements, tabula_data: dict, threshold: float = 0.1) -> str | None:
    """Validate an element's U-value against a Tabula reference dataset.

    Returns a warning string if the computed U-value falls outside
    the acceptable range of the reference value, or None if it passes.

    Args:
        element: Elements instance to validate.
        tabula_data: Reference dict keyed by archetype (e.g. TABULA_CMF).
        threshold: Fractional tolerance either side of the reference value
                   (default 0.1 = +/- 10%).

    Returns:
        Warning string if outside tolerance, or None if within range or
        no matching reference value found.
    """
    match = match_tabula(element, tabula_data)
    if match is None:
        return None
    matched_archetype, matched_type = match
    tabula_u = tabula_data[matched_archetype][matched_type]
    if element.u_value > tabula_u * (1+threshold ) or  element.u_value < tabula_u * (1-threshold ):  # only warn if outside of range
        return (
            f"U-value {element.u_value:.4f} is not within Tabula Range (+- {threshold*100:.0f}%) of "
            f"{tabula_u} for {matched_archetype} {matched_type}"
        )
    return None