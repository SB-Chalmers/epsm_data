"""Reference standards and validation tolerances.

Owns TABULA reference data, lookup helpers, and tolerance-band
validation for computed U-values.
"""

from __future__ import annotations

from epsm_data.domain.enums import BuildingElement

# ──────────────────────────────────────────────────────────────────
# TABULA reference U-values by archetype key and element type.
# ──────────────────────────────────────────────────────────────────
TABULA_CMF: dict[str, dict[str, float]] = {
    "CMF_1940": {"roof": 0.36, "wall": 0.58, "window": 2.22, "floor": 0.32, "basement_wall": 0.70},
    "CMF_1950": {"roof": 0.36, "wall": 0.58, "window": 2.22, "floor": 0.32, "basement_wall": 0.70},
    "CMF_1960": {"roof": 0.20, "wall": 0.41, "window": 2.22, "floor": 0.26, "basement_wall": 0.70},
    "CMF_1970": {"roof": 0.20, "wall": 0.41, "window": 2.22, "floor": 0.26, "basement_wall": 0.70},
    "CMF_1980": {"roof": 0.17, "wall": 0.33, "window": 2.04, "floor": 0.27, "basement_wall": 0.70},
    "CMF_1990": {"roof": 0.15, "wall": 0.22, "window": 1.80, "floor": 0.24, "basement_wall": 0.70},
}

REFERENCE_U_VALUES = TABULA_CMF  # convenience alias

# Default tolerance for TABULA validation (±20%)
DEFAULT_TOLERANCE = 0.2

# Maps BuildingElement → TABULA element-type key
TABULA_TYPE_MAP: dict[BuildingElement, str] = {
    BuildingElement.EXT_WALL: "wall",
    BuildingElement.EXT_WALL_LOW: "wall",
    BuildingElement.EXT_WALL_MEDIUM: "wall",
    BuildingElement.EXT_WALL_HIGH: "wall",
    BuildingElement.GROUND_FLOOR: "floor",
    BuildingElement.ROOF: "roof",
}


# ──────────────────────────────────────────────────────────────────
# Lookup helpers
# ──────────────────────────────────────────────────────────────────

def _match_tabula(
    element_name: str,
    application: BuildingElement,
    tabula_data: dict[str, dict[str, float]] = TABULA_CMF,
) -> tuple[str, str] | None:
    """Resolve archetype key and element type in TABULA data."""
    name_upper = element_name.upper()
    matched_archetype = next(
        (k for k in tabula_data if k.upper() in name_upper), None
    )
    if matched_archetype is None:
        return None
    matched_type = TABULA_TYPE_MAP.get(application)
    if matched_type is None:
        return None
    return matched_archetype, matched_type


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


def get_tabula_u_value(
    element_name: str,
    application: BuildingElement,
) -> float | None:
    """Reference U-value for an element, or None if no TABULA match."""
    match = _match_tabula(element_name, application)
    if match is None:
        return None
    archetype_key, element_type = match
    return TABULA_CMF[archetype_key][element_type]


def get_window_reference_u_value(window_name: str) -> float | None:
    """TABULA reference window U-value, or None if archetype unknown."""
    matched = next(
        (k for k in TABULA_CMF if k.upper() in window_name.upper()), None
    )
    if matched and "window" in TABULA_CMF[matched]:
        return TABULA_CMF[matched]["window"]
    return None


# ──────────────────────────────────────────────────────────────────
# Validation
# ──────────────────────────────────────────────────────────────────

def validate_against_reference(
    element_name: str,
    application: BuildingElement,
    u_value: float,
    tolerance: float = DEFAULT_TOLERANCE,
    tabula_data: dict[str, dict[str, float]] | None = None,
) -> str | None:
    """Check element U-value against TABULA reference.

    Returns a warning string if outside the tolerance band, else None.
    """
    data = tabula_data if tabula_data is not None else TABULA_CMF
    match = _match_tabula(element_name, application, data)
    if match is None:
        return None
    archetype_key, element_type = match
    tabula_u = data[archetype_key][element_type]
    if u_value > tabula_u * (1 + tolerance) or u_value < tabula_u * (1 - tolerance):
        return (
            f"U-value {u_value:.4f} outside TABULA range "
            f"(+/-{tolerance * 100:.0f}%) of {tabula_u} "
            f"for {archetype_key} {element_type}"
        )
    return None
