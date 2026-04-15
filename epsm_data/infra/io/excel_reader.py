"""Excel reader for Material_Database.xlsx.

Parses source workbook sheets, normalises columns, filters ignored
rows, and returns transport DTOs.  No domain-object construction or
cross-referencing happens here.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from .dto import (
    BuildingRow,
    ComponentLayerRef,
    ComponentRow,
    ElementRow,
    LayerMaterialSlot,
    LayerRow,
    MaterialRow,
    ReadResult,
)

logger = logging.getLogger(__name__)


def _parse_construction_year(archetype: str) -> int | None:
    """Extract a 4-digit year from an archetype name (e.g. 'CMF_1960_1' → 1960)."""
    for part in archetype.split("_"):
        if part.isdigit() and len(part) == 4:
            return int(part)
    return None

# ── column templates per sheet ────────────────────────────────────

_MATERIAL_COLS = [
    "Material Name",
    "Ignore?",
    "Boverket ID",
    "Boverket Match Confidence",
    "Honeybee Identifier",
    "Honeybee Match Confidence",
    "Combined Match Confidence",
]

_LAYER_COLS = [
    "Layer Code",
    "Layer Thickness",
    "Composite Layer?",
    "Material 1",
    "Material 1 Area Ratio",
    "Material 2",
    "Material 2 Area Ratio",
    "Material 3",
    "Material 3 Area Ratio",
    "Notes",
    "Ignore?",
    "Layer Use Intensity",
    "Duplicate Check",
]

_COMPONENT_COLS = [
    "Component Code",
    "Layers",
    "Application",
    "Layer Index",
    "Shearing Layer",
    "Archetype",
    "Notes",
    "Flag",
]

_BUILDING_ELEMENT_ROLES = [
    "Roof",
    "Top Floor",
    "Intermediate Floor",
    "Ground Floor",
    "Basement Floor",
    "Ext Wall",
    "Ext Wall Low",
    "Ext Wall Medium",
    "Ext Wall High",
    "Basement Wall",
    "Int Wall Loadbearing",
    "Int Wall Nonloadbearing",
]

_BUILDING_SKIP_VALUES = frozenset(
    {"not required", "no components assigned to this element", "no match", ""}
)

# ── helpers ───────────────────────────────────────────────────────


def _is_ignored(row: pd.Series, col: str = "Ignore?") -> bool:
    val = row.get(col)
    return pd.notna(val) and str(val).strip().upper() == "X"


def _clean(val: object) -> str | None:
    """Return a stripped string or *None* for blank / NaN values."""
    if pd.isna(val):
        return None
    s = str(val).strip()
    return s if s else None


# ── public readers ────────────────────────────────────────────────


def read_material_sheet(path: Path) -> ReadResult[MaterialRow]:
    """Read the *Opaque_Materials* sheet."""
    df = pd.read_excel(path, sheet_name="Opaque_Materials", header=1)
    df.columns = _MATERIAL_COLS

    records: list[MaterialRow] = []
    skipped: list[tuple[str, str]] = []

    for _, row in df.iterrows():
        name = _clean(row.get("Material Name")) or "Unknown"

        if _is_ignored(row):
            skipped.append((name, "Marked as ignored"))
            continue

        boverket_id = _clean(row.get("Boverket ID"))
        honeybee_id = _clean(row.get("Honeybee Identifier"))

        if not boverket_id:
            skipped.append((name, "No Boverket ID"))
            continue
        if not honeybee_id:
            skipped.append((name, "No Honeybee Identifier"))
            continue

        records.append(
            MaterialRow(name=name, boverket_id=boverket_id, honeybee_id=honeybee_id)
        )

    logger.info("Opaque_Materials — loaded: %d, skipped: %d", len(records), len(skipped))
    for n, reason in skipped:
        logger.debug("  skipped '%s': %s", n, reason)

    return ReadResult(records=records, skipped=skipped)


def read_layer_sheet(path: Path) -> ReadResult[LayerRow]:
    """Read the *Layers* sheet."""
    df = pd.read_excel(path, sheet_name="Layers", header=1)
    df.columns = _LAYER_COLS

    records: list[LayerRow] = []
    skipped: list[tuple[str, str]] = []

    for _, row in df.iterrows():
        code = _clean(row.get("Layer Code"))
        if not code:
            continue

        if _is_ignored(row):
            skipped.append((code, "Marked as ignored"))
            continue

        thickness_raw = row.get("Layer Thickness")
        if pd.isna(thickness_raw):
            skipped.append((code, "Missing thickness"))
            continue
        try:
            thickness = float(str(thickness_raw).replace(",", "."))
        except ValueError:
            skipped.append((code, f"Invalid thickness: '{thickness_raw}'"))
            continue

        is_composite = str(row.get("Composite Layer?", "S")).strip().upper() == "C"

        materials: list[LayerMaterialSlot] = []
        parse_error: str | None = None

        for idx in (1, 2, 3):
            mat_name = _clean(row.get(f"Material {idx}"))
            if mat_name is None:
                break

            frac_raw = row.get(f"Material {idx} Area Ratio")
            frac: float | None = None
            if pd.notna(frac_raw) and str(frac_raw).strip():
                try:
                    frac = float(str(frac_raw).replace(",", "."))
                except ValueError:
                    parse_error = f"Material {idx} '{mat_name}': invalid area ratio"
                    break

            materials.append(LayerMaterialSlot(material_name=mat_name, area_fraction=frac))

        if parse_error:
            skipped.append((code, parse_error))
            continue
        if not materials:
            skipped.append((code, "No valid materials"))
            continue
        if is_composite and len(materials) < 2:
            skipped.append((code, "Composite but fewer than 2 materials"))
            continue
        if not is_composite and len(materials) > 1:
            skipped.append((code, "Multiple materials but not composite"))
            continue

        records.append(
            LayerRow(
                layer_code=code,
                thickness=thickness,
                is_composite=is_composite,
                materials=tuple(materials),
            )
        )

    logger.info("Layers — loaded: %d, skipped: %d", len(records), len(skipped))
    for n, reason in skipped:
        logger.debug("  skipped '%s': %s", n, reason)

    return ReadResult(records=records, skipped=skipped)


def read_component_sheet(path: Path) -> ReadResult[ComponentRow]:
    """Read the *Components* sheet, grouping rows by component code."""
    df = pd.read_excel(path, sheet_name="Components", header=1)
    df.columns = _COMPONENT_COLS
    df["Component Code"] = df["Component Code"].ffill()

    records: list[ComponentRow] = []
    skipped: list[tuple[str, str]] = []

    for comp_code, group in df.groupby("Component Code", sort=False):
        comp_code = str(comp_code).strip()

        layers: list[ComponentLayerRef] = []
        parse_error: str | None = None

        for _, row in group.iterrows():
            layer_code = _clean(row.get("Layers"))
            if layer_code is None:
                logger.debug("  '%s': blank layer row skipped", comp_code)
                continue
            try:
                index = int(row.get("Layer Index"))
            except (ValueError, TypeError):
                parse_error = f"Invalid layer index for '{layer_code}'"
                break

            layers.append(ComponentLayerRef(layer_code=layer_code, layer_index=index))

        if parse_error or not layers:
            skipped.append((comp_code, parse_error or "No valid layers"))
            continue

        layers.sort(key=lambda x: x.layer_index)

        first = group.iloc[0]
        application = (_clean(first.get("Application")) or "").upper()
        shearing = (_clean(first.get("Shearing Layer")) or "").capitalize()
        archetype = _clean(first.get("Archetype")) or ""

        records.append(
            ComponentRow(
                component_code=comp_code,
                archetype=archetype,
                application=application,
                shearing_layer=shearing,
                layers=tuple(layers),
            )
        )

    logger.info("Components — loaded: %d, skipped: %d", len(records), len(skipped))
    for n, reason in skipped:
        logger.debug("  skipped '%s': %s", n, reason)

    return ReadResult(records=records, skipped=skipped)


def read_element_sheet(path: Path) -> ReadResult[ElementRow]:
    """Read the *Elements* sheet."""
    df = pd.read_excel(path, sheet_name="Elements", header=1)

    fixed_cols = ["Element Code", "Element Type", "Archetype"]
    component_cols = [f"Component {i}" for i in range(1, len(df.columns) - 2)]
    df.columns = fixed_cols + component_cols

    records: list[ElementRow] = []
    skipped: list[tuple[str, str]] = []

    for _, row in df.iterrows():
        code = _clean(row.get("Element Code"))
        if not code:
            continue

        archetype = _clean(row.get("Archetype")) or ""
        el_type = (_clean(row.get("Element Type")) or "").upper()

        year = _parse_construction_year(archetype)
        if year is None:
            skipped.append((code, f"Could not parse year from '{archetype}'"))
            continue

        comp_codes: list[str] = []
        no_match = False

        for col in component_cols:
            val = _clean(row.get(col))
            if val is None:
                continue
            if val == "No matches found":
                skipped.append((code, "No matches found"))
                no_match = True
                break
            comp_codes.append(val)

        if no_match:
            continue
        if not comp_codes:
            skipped.append((code, "No components found"))
            continue

        records.append(
            ElementRow(
                element_code=code,
                element_type=el_type,
                archetype=archetype,
                construction_year=year,
                component_codes=tuple(comp_codes),
            )
        )

    logger.info("Elements — loaded: %d, skipped: %d", len(records), len(skipped))
    for n, reason in skipped:
        logger.debug("  skipped '%s': %s", n, reason)

    return ReadResult(records=records, skipped=skipped)


def read_building_sheet(path: Path) -> ReadResult[BuildingRow]:
    """Read the *Building* sheet."""
    df = pd.read_excel(path, sheet_name="Building", header=1)
    df.columns = ["Archetype", "Multiple Ext Walls"] + _BUILDING_ELEMENT_ROLES

    records: list[BuildingRow] = []
    skipped: list[tuple[str, str]] = []

    for _, row in df.iterrows():
        archetype = _clean(row.get("Archetype"))
        if not archetype:
            continue

        year = _parse_construction_year(archetype)
        if year is None:
            skipped.append((archetype, f"Could not parse year from '{archetype}'"))
            continue

        multi = str(row.get("Multiple Ext Walls", "")).strip().lower() == "yes"

        assignments: list[tuple[str, str]] = []
        for role in _BUILDING_ELEMENT_ROLES:
            val = _clean(row.get(role))
            if val is None or val.lower() in _BUILDING_SKIP_VALUES:
                continue
            assignments.append((role, val))

        if not assignments:
            skipped.append((archetype, "No elements assigned"))
            continue

        records.append(
            BuildingRow(
                archetype=archetype,
                construction_year=year,
                multiple_ext_walls=multi,
                element_assignments=tuple(assignments),
            )
        )

    logger.info("Buildings — loaded: %d, skipped: %d", len(records), len(skipped))
    for n, reason in skipped:
        logger.debug("  skipped '%s': %s", n, reason)

    return ReadResult(records=records, skipped=skipped)
