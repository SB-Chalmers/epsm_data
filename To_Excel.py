"""
Utility script that mirrors the material classes defined in ``Materials.py`` and
creates an Excel template where each class gets its own worksheet. The template
pre-populates column headers, brief field descriptions (via cell comments) and
data validation lists for enumerations such as ``Roughness``.

Example:
    python To_Excel.py --output EPSM_material_template.xlsx --overwrite
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
except ImportError as exc:  # pragma: no cover - defensive guard
    raise SystemExit(
        "The 'openpyxl' package is required to build the Excel template. "
        "Install it with 'pip install openpyxl' and re-run the script."
    ) from exc

from EPSM_Enums import Roughness


DEFAULT_OUTPUT = Path(__file__).with_name("material_template.xlsx")
MAX_VALIDATION_ROWS = 500  # Limit span of data validation ranges per column.
HEADER_FONT = Font(size=12, bold=True, name="Calibri")
DESCRIPTION_FONT = Font(size=10, italic=True, name="Calibri")
HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=False)
DESCRIPTION_ALIGNMENT = Alignment(horizontal="left", vertical="center", wrap_text=True)
HEADER_ROW_HEIGHT = 22
DESCRIPTION_ROW_HEIGHT = 36
HEADER_FILL = PatternFill(fill_type="solid", fgColor="808080")
DESCRIPTION_FILL = PatternFill(fill_type="solid", fgColor="D3D3D3")


@dataclass(frozen=True)
class FieldSpec:
    """Definition for a column in the Excel template."""

    name: str
    description: str
    required: bool = True
    choices: Optional[List[str]] = None
    lookup_name: Optional[str] = None


BASE_FIELDS: List[FieldSpec] = [
    FieldSpec(
        name="UUID",
        description="Globally unique identifier for the material entry.",
    ),
    FieldSpec(
        name="Material Name",
        description="Human-readable material name for the matched material.",
    ),
    FieldSpec(
        name="EnergyPlus Material Type",
        description="EnergyPlus material object type (e.g., EnergyMaterial, WindowMaterial:SimpleGlazing).",
    ),
    FieldSpec(
        name="Thermal Conductivity [W/mK]",
        description="Thermal conductivity in W/mK.",
    ),
    FieldSpec(
        name="A1-A3 Impact Conservative",
        description="For LCA purposes. This should be a conservative value inherited from Boverkets Klimatdatabas.",
        required=False,
    ),
    FieldSpec(
        name="A1-A3 Impact Unit",
        description="Unit for the GWP (A1-A3), most commonly kgCO2/kg material (e.g. kgCO2/kg, kgCO2/m3, kgCO2/m2)",
        required=False,
    ),
    FieldSpec(
        name="A4 Impact Conservative",
        description="For LCA purposes. This should be a conservative value inherited from Boverkets Klimatdatabas.",
        required=False,
    ),
    FieldSpec(
        name="A4 Impact Unit",
        description="Unit for the GWP (A4), most commonly kgCO2/kg material (e.g. kgCO2/kg, kgCO2/m3, kgCO2/m2)",
        required=False,
    ),
    FieldSpec(
        name="A5 Impact Conservative",
        description="For LCA purposes. This should be a conservative value inherited from Boverkets Klimatdatabas.",
        required=False,
    ),
    FieldSpec(
        name="A5 Impact Unit",
        description="Unit for the GWP (A5), most commonly kgCO2/kg material (e.g. kgCO2/kg, kgCO2/m3, kgCO2/m2)",
        required=False,
    ),

]

OPAQUE_SPECIFIC_FIELDS: List[FieldSpec] = [
    FieldSpec(
        name="Roughness",
        description="Surface roughness classification as defined in Honeybee Material Library.",
        choices=[r.value for r in Roughness],
        lookup_name="Roughness",
    ),
    FieldSpec(
        name="Density",
        description="Material density.",
    ),
    FieldSpec(
        name="Density Unit",
        description="Most common in kg/m3. Other possible are kg/m2.",
    ),
    FieldSpec(
        name="Specific Heat Capacity [J/kgK]",
        description="Specific heat capacity in J/kgK.",
    ),
    FieldSpec(
        name="Thermal Absorptance",
        description="Thermal absorptance (0-1).",
    ),
    FieldSpec(
        name="Solar Absorptance",
        description="Solar absorptance (0-1).",
    ),
    FieldSpec(
        name="Visible Absorptance",
        description="Visible absorptance (0-1).",
    ),
]

WINDOW_SPECIFIC_FIELDS: List[FieldSpec] = [
    FieldSpec(
        name="Solar Transmittance",
        description="Solar transmittance (0-1).",
    ),
    FieldSpec(
        name="Solar Reflectance",
        description="Front solar reflectance (0-1).",
    ),
    FieldSpec(
        name="Solar Reflectance Back",
        description="Back solar reflectance (0-1).",
    ),
    FieldSpec(
        name="Visible Transmittance",
        description="Visible transmittance (0-1).",
    ),
    FieldSpec(
        name="Visible Reflectance",
        description="Front visible reflectance (0-1).",
    ),
    FieldSpec(
        name="Visible Reflectance Back",
        description="Back visible reflectance (0-1).",
    ),
    FieldSpec(
        name="Infrared Transmittance",
        description="Infrared transmittance (0-1).",
    ),
    FieldSpec(
        name="Emissivity",
        description="Front emissivity (0-1).",
    ),
    FieldSpec(
        name="Emissivity Back",
        description="Back emissivity (0-1).",
    ),
    FieldSpec(
        name="Dirt Correction",
        description="Dirt correction factor (typically 1.0).",
    ),
    FieldSpec(
        name="Solar Diffusing",
        description="Whether the glazing diffuses solar radiation (True/False).",
        choices=["True", "False"],
    ),
]

SHEET_SPECS = {
    "OpaqueMaterial": {
        "description": "Use for opaque materials (inherits OpaqueMaterial in Materials.py).",
        "fields": BASE_FIELDS + OPAQUE_SPECIFIC_FIELDS,
    },
    "WindowMaterial": {
        "description": "Use for transparent/window materials (inherits WindowMaterial in Materials.py).",
        "fields": BASE_FIELDS + WINDOW_SPECIFIC_FIELDS,
    },
}

LOOKUP_VALUES = {
    "Roughness": [enum.value for enum in Roughness],
}


def build_template(output_path: Path) -> Path:
    """Create the Excel template and save it to *output_path*."""
    wb = Workbook()
    overview_ws = wb.active
    overview_ws.title = "Overview"
    _populate_overview_sheet(overview_ws)
    lookup_ranges = _add_lookup_sheet(wb)

    for sheet_name, spec in SHEET_SPECS.items():
        ws = wb.create_sheet(title=sheet_name)
        _populate_material_sheet(ws, spec["fields"], lookup_ranges)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return output_path


def _populate_overview_sheet(ws) -> None:
    ws["A1"] = "EPSM Material Database Template"
    ws["A2"] = f"Generated on: {datetime.now():%Y-%m-%d %H:%M}"
    ws["A4"] = "Sheet"
    ws["B4"] = "Description"
    row = 5
    for sheet_name, spec in SHEET_SPECS.items():
        ws.cell(row=row, column=1, value=sheet_name)
        ws.cell(row=row, column=2, value=spec["description"])
        row += 1
    ws["A{row}".format(row=row + 1)] = "Lookups"
    ws["B{row}".format(row=row + 1)] = "Reference enumerations used by data validation."
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 80


def _add_lookup_sheet(wb: Workbook) -> Dict[str, str]:
    ws = wb.create_sheet(title="Lookups")
    lookup_ranges: Dict[str, str] = {}
    for col_index, (name, values) in enumerate(LOOKUP_VALUES.items(), start=1):
        column_letter = get_column_letter(col_index)
        ws.cell(row=1, column=col_index, value=name)
        for row_offset, value in enumerate(values, start=2):
            ws.cell(row=row_offset, column=col_index, value=value)
        last_row = len(values) + 1
        lookup_ranges[name] = f"'Lookups'!${column_letter}$2:${column_letter}${last_row}"
        ws.column_dimensions[column_letter].width = max(len(name), *(len(v) for v in values)) + 2
    return lookup_ranges


def _populate_material_sheet(
    ws, fields: Iterable[FieldSpec], lookup_ranges: Dict[str, str]
) -> None:
    field_list = list(fields)
    ws.append([field.name for field in field_list])
    ws.append(
        [
            f"{'Required' if field.required else 'Optional'}: {field.description}"
            for field in field_list
        ]
    )
    ws.freeze_panes = "A3"
    ws.row_dimensions[1].height = HEADER_ROW_HEIGHT
    ws.row_dimensions[2].height = DESCRIPTION_ROW_HEIGHT

    for index, field in enumerate(field_list, start=1):
        column_letter = get_column_letter(index)
        header_cell = ws.cell(row=1, column=index)
        desc_cell = ws.cell(row=2, column=index)
        header_cell.font = HEADER_FONT
        header_cell.alignment = HEADER_ALIGNMENT
        desc_cell.font = DESCRIPTION_FONT
        desc_cell.alignment = DESCRIPTION_ALIGNMENT
        header_cell.fill = HEADER_FILL
        desc_cell.fill = DESCRIPTION_FILL
        width_candidates = [
            len(field.name) + 2,
            len(field.description) + 4,
            16,
        ]
        ws.column_dimensions[column_letter].width = min(max(width_candidates), 50)
        _apply_data_validation(ws, column_letter, field, lookup_ranges)


def _apply_data_validation(
    ws, column_letter: str, field: FieldSpec, lookup_ranges: Dict[str, str]
) -> None:
    if field.lookup_name and field.lookup_name in lookup_ranges:
        formula = lookup_ranges[field.lookup_name]
    elif field.choices:
        formula = '"' + ",".join(field.choices) + '"'
    else:
        return

    target_range = f"${column_letter}$3:${column_letter}${MAX_VALIDATION_ROWS}"
    dv = DataValidation(type="list", formula1=formula, allow_blank=not field.required)
    ws.add_data_validation(dv)
    dv.add(target_range)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create an Excel template that mirrors the EPSM material classes."
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Path for the generated template (default: {DEFAULT_OUTPUT.name}).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting an existing template at the target path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path: Path = args.output.expanduser().resolve()
    created_path = build_template(output_path)
    print(f"Template written to {created_path}")

if __name__ == "__main__":
    main()
