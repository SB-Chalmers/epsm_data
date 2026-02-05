# python -m ExtractingMaterials.ExtractEnergyPlus
import json
import os
from datetime import datetime
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
OUTPUT_DIR = os.path.join(BASE_DIR, "output")


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_opaque_materials_from_excel(filename: str):
    excel_path = os.path.join(PROJECT_ROOT, filename)
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    df = pd.read_excel(excel_path, sheet_name="Opaque_Materials")

    # Normalize column names
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace("_", " ")
    )

    required_columns = {
        "material name",
        "energyplus identifier",
    }

    if not required_columns.issubset(df.columns):
        raise ValueError(
            f"Excel must contain columns: {required_columns}. "
            f"Found: {set(df.columns)}"
        )

    opaque_json = load_json(os.path.join(BASE_DIR, "opaque_material.json"))

    extracted = {}
    skipped = []

    for _, row in df.iterrows():
        material_name = row.get("material name")
        ep_id = row.get("energyplus identifier")

        # Skip empty or NaN cells
        if pd.isna(material_name) or pd.isna(ep_id):
            skipped_name = str(material_name).strip() if pd.notna(material_name) else "Unknown"
            skipped.append(skipped_name)
            continue

        material_name = str(material_name).strip()
        ep_id = str(ep_id).strip()

        mat_data = opaque_json.get(ep_id)
        if mat_data is None:
            skipped.append(material_name)
            print(f"Skipping '{material_name}': EP ID '{ep_id}' not found")
            continue

        # Copy the material and overwrite identifier with the material name
        mat_copy = mat_data.copy()
        mat_copy["identifier"] = material_name
        extracted[material_name] = mat_copy

    return extracted, skipped


def filter_materials_by_archetype(excel_file: str, materials_json: dict, archetype: str = None):
    if archetype is None:
        # No filtering, return all materials
        return materials_json.copy()

    # Read the Layer sheet from the Excel file
    df_layers = pd.read_excel(excel_file, sheet_name="Layers")
    
    # Filter layers for the archetype
    df_filtered = df_layers[df_layers['Archetype'] == archetype]

    # Collect all materials from Material 1, 2, 3...
    material_cols = [col for col in df_filtered.columns if col.startswith("Material")]
    material_names = set()
    for col in material_cols:
        names = df_filtered[col].dropna().astype(str).str.strip()
        material_names.update(names)

    # Keep only materials that exist in extracted JSON
    filtered_materials = {
        name: data
        for name, data in materials_json.items()
        if name in material_names
    }

    return filtered_materials

def export_materials(materials: dict):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    today = datetime.today().strftime("%Y-%m-%d")
    output_path = os.path.join(
        OUTPUT_DIR, f"Extracted_EnergyPlus_ALL_{today}.json" #json name
    )

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(materials, f, indent=4)

    print(f"Exported → {output_path}")


if __name__ == "__main__":
    excel_file = "Material_Database.xlsx"

    # Load all opaque materials
    materials, skipped = load_opaque_materials_from_excel(excel_file)

    # Choose archetype to extract, or None to export all materials
    archetype_to_extract = "CMF_1950"  # <-- change to "CMF_1940_1" or None for all

    filtered_materials = filter_materials_by_archetype(
        excel_file=os.path.join(PROJECT_ROOT, excel_file),
        materials_json=materials,
        archetype=archetype_to_extract
    )

    export_materials(filtered_materials)

    # Print summary
    print("\nSummary:")
    print(f"- Extracted materials (all): {len(materials)}")
    print(f"- Skipped materials: {len(skipped)}")
    if archetype_to_extract:
        print(f"- Materials for archetype '{archetype_to_extract}': {len(filtered_materials)}")
    else:
        print(f"- Materials exported (no archetype filter): {len(filtered_materials)}")

    if skipped:
        print("\nSkipped:")
        for name in skipped:
            print(f"- {name}")
