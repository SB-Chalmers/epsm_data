"""Excel reader.

Expected responsibilities:
- Parse source workbook sheets.
- Normalize columns.
- Return transport DTOs only (no domain object construction).
"""

import pandas as pd


def read_opaque_materials_sheet(excel_path: str) -> pd.DataFrame:
    """Read and normalize the Opaque_Materials sheet.

    Args:
        excel_path: Path to the Excel workbook.

    Returns:
        Normalized DataFrame with columns: Material Name, Ignore?, Boverket ID,
        Boverket Match Confidence, Honeybee Identifier, Honeybee Match Confidence,
        Combined Match Confidence.
    """
    df = pd.read_excel(excel_path, sheet_name="Opaque_Materials", header=0)
    df = df.drop(index=0).reset_index(drop=True)
    df.columns = [
        "Material Name", "Ignore?", "Boverket ID", "Boverket Match Confidence",
        "Honeybee Identifier", "Honeybee Match Confidence", "Combined Match Confidence",
    ]
    return df


def _mat_part(series: pd.Series) -> pd.Series:
    """Convert a material name column to an uppercase prefix with trailing underscore, or empty string."""
    return series.fillna("").astype(str).str.strip().str.upper().apply(
        lambda x: x + "_" if x not in ("", "NAN", "NONE") else ""
    )

def read_layers_sheet(excel_path: str) -> pd.DataFrame:
    """Read and normalize the Layers sheet."""
    df = pd.read_excel(excel_path, sheet_name="Layers", header=0)
    df = df.drop(index=0).reset_index(drop=True)
    df.columns = [
        "Layer Code", "Layer Thickness", "Composite Layer?",
        "Material 1", "Material 1 Area Ratio",
        "Material 2", "Material 2 Area Ratio",
        "Material 3", "Material 3 Area Ratio",
        "Notes", "Ignore?", "Layer Use Intensity", "Duplicate Check",
    ]

    def thickness_to_code(t) -> str:
        """Replicate Excel TEXTAFTER(thickness, ',') — digits after decimal point."""
        s = str(t).strip()
        if "." in s:
            return s.split(".")[1].rstrip("0") or "0"
        return s

    df["Layer Code"] = (
        _mat_part(df["Material 1"])
        + _mat_part(df["Material 2"])
        + _mat_part(df["Material 3"])
        + df["Layer Thickness"].apply(thickness_to_code)
        + "_"
        + df["Composite Layer?"].fillna("").astype(str).str.strip().str.upper()
    )
    return df


def read_components_sheet(excel_path: str) -> pd.DataFrame:
    """Read and normalize the Components sheet.

    Args:
        excel_path: Path to the Excel workbook.

    Returns:
        Normalized DataFrame with columns: Component Code, Layers,
        Application, Layer Index, Shearing Layer, Archetype, Notes, Flag.
    """
    df = pd.read_excel(excel_path, sheet_name="Components", header=0)
    df = df.drop(index=0).reset_index(drop=True)
    df.columns = [
        "Component Code", "Layers", "Application", "Layer Index",
        "Shearing Layer", "Archetype", "Notes", "Flag",
    ]
    # Component Code is a formula — reconstruct from Archetype + Application + ShearingLayer
    # Every row has its own formula so no ffill needed
    df["Component Code"] = (
        df["Archetype"].fillna("").astype(str).str.strip()
        + "_"
        + df["Application"].fillna("").astype(str).str.strip()
        + "_"
        + df["Shearing Layer"].fillna("").astype(str).str.strip().str.upper()
    )
    # ffill only where Archetype is blank (continuation rows for same component)
    df["Component Code"] = df["Component Code"].where(
        df["Archetype"].notna(), other=None
    ).ffill()
    return df


def read_elements_sheet(excel_path: str) -> pd.DataFrame:
    """Read and normalize the Elements sheet.

    Dynamically assigns component columns based on workbook width.

    Args:
        excel_path: Path to the Excel workbook.

    Returns:
        Normalized DataFrame with columns: Element Code, Element Type,
        Archetype, Component 1..N.
    """
    df = pd.read_excel(excel_path, sheet_name="Elements", header=0)
    df = df.drop(index=0).reset_index(drop=True)
    fixed_cols = ["Element Code", "Element Type", "Archetype"]
    component_cols = [f"Component {i}" for i in range(1, len(df.columns) - 2)]
    df.columns = fixed_cols + component_cols
    # Element Code is a formula — reconstruct from Archetype + Element Type
    df["Element Code"] = (
        df["Archetype"].astype(str).str.strip()
        + "_"
        + df["Element Type"].astype(str).str.strip()
    )
    return df


def read_window_elements_sheet(excel_path: str) -> pd.DataFrame:
    """Read and normalize the Window_Element sheet.

    Args:
        excel_path: Path to the Excel workbook.

    Returns:
        Normalized DataFrame with columns: Material Name, Boverket ID,
        Boverket Match Confidence, HoneyBee Identifier Opaque,
        HoneyBee Match Confidence, HoneyBee Identifier Window Construction,
        Honeybee Match Confidence, Combined Match Confidence,
        Glazing Unit, Thickness, PANE SIZE, Comments.
    """
    df = pd.read_excel(excel_path, sheet_name="Window_Element", header=0)
    df.columns = [
        "Material Name", "Boverket ID", "Boverket Match Confidence",
        "HoneyBee Identifier Opaque", "HoneyBee Match Confidence",
        "HoneyBee Identifier Window Construction", "Honeybee Match Confidence",
        "Combined Match Confidence", "Glazing Unit", "Thickness",
        "PANE SIZE", "Comments",
    ]
    df = df.drop(index=0).reset_index(drop=True)
    return df


def read_buildings_sheet(excel_path: str) -> pd.DataFrame:
    """Read and normalize the Building sheet.

    Args:
        excel_path: Path to the Excel workbook.

    Returns:
        Normalized DataFrame with columns: Archetype, Multiple Ext Walls,
        element type columns, Window element, and WWR/infiltration columns.
    """
    df = pd.read_excel(excel_path, sheet_name="Building", header=0)
    df = df.drop(index=0).reset_index(drop=True)
    df.columns = [str(c).strip() for c in df.columns]

    rename_map = {
        "Archetype Code": "Archetype",
        "Multiple Exterior Wall defenitions?": "Multiple Ext Walls",
        "Roof Element": "Roof",
        "Top Floor Element": "Top Floor",
        "Intermediate Floor Element": "Intermediate Floor",
        "Ground Floor Element": "Ground Floor",
        "Basement Floor Element": "Basement Floor",
        "Exterior Wall Element": "Ext Wall",
        "Exterior Wall Low Element": "Ext Wall Low",
        "Exterior Wall Medium Element": "Ext Wall Medium",
        "Exterior Wall High Element": "Ext Wall High",
        "Basement Wall Element": "Basement Wall",
        "Interior Wall Loadbearing Element": "Int Wall Loadbearing",
        "Interior Wall Non Loadbearing Element": "Int Wall Nonloadbearing",
        "Window element": "Window element",
        "Infiltration rate": "Infiltration rate",
        "Ventilation System": "Ventilation System",
        "Cold attic?": "Cold attic",
    }
    df = df.rename(columns=rename_map)
    return df