# python -m ExtractingMaterials.ExtractExcel
import json
import os
from datetime import datetime

import pandas as pd

from EPSM_Enums import EmbodiedCarbon, Roughness
from ClassDefinitions.Materials import OpaqueMaterial

# Base directory of this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
OUTPUT_DIR = os.path.join(BASE_DIR, "output")


def load_json(path: str):
    """Load JSON file from given path."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_by_resource_id(boverket_list, resource_id):
    """Find Boverket entry by ResourceId."""
    for item in boverket_list:
        if str(item.get("ResourceId")) == str(resource_id):
            return item
    return None


def create_embodied_carbon(data: dict) -> EmbodiedCarbon:
    """Instantiate the EmbodiedCarbon class from Boverket JSON entry."""
    data_items = data.get("DataItems", [])
    if not data_items:
        raise ValueError("No DataItems found in Boverket entry")

    gwp = data_items[0].get("DataValueItems", [])

    def get_value(code_name):
        for v in gwp:
            if v["DataModuleCode"] == code_name:
                return v["Value"]
        return 0

    tsl_str = str(data.get("RefServiceLifeNormal", ">50"))
    try:
        tsl = int(tsl_str.strip(">").split()[0])
    except Exception:
        tsl = 50

    return EmbodiedCarbon(
        product_name=data.get("Name", "Unknown"),
        resource_id=str(data.get("ResourceId")),
        A1_A3_conservative=get_value("A1-A3 Conservative"),
        A4=get_value("A4"),
        A5_conservative=get_value("A5.1"),
        A1_A3_typical=get_value("A1-A3 Typical"),
        A1_A3_factor_conservative=float(
            data.get("ConservativeDataConversionFactor", 1)
        ),
        A5_factor_byggspill=float(data.get("WasteFactor", 1)),
        conversion_factor=float(
            data.get("Conversions", [{}])[0].get("Value", 1)
        ),
        technical_service_life=tsl
    )


def create_opaque_material(mat_data: dict, ec: EmbodiedCarbon, material_name: str) -> OpaqueMaterial:
    """Instantiate OpaqueMaterial and override name from Excel."""
    try:
        roughness_enum = next(
            r for r in Roughness if r.value == mat_data["roughness"]
        )
    except StopIteration:
        raise ValueError(f"Unknown roughness value: {mat_data['roughness']}")

    return OpaqueMaterial(
        roughness=roughness_enum,
        density=mat_data["density"],
        specific_heat=mat_data["specific_heat"],
        thermal_absorptance=mat_data["thermal_absorptance"],
        solar_absorptance=mat_data["solar_absorptance"],
        visible_absorptance=mat_data["visible_absorptance"],
        conductivity=mat_data["conductivity"],
        name=material_name,              # ← FROM EXCEL
        mat_type=mat_data.get("type", "EnergyMaterial"),
        embodied_carbon=ec,
        json_id=material_name,            # ← stable JSON key
        boverket_id=ec.resource_id
    )


def extract_material(boverket_id: str, ep_id: str, material_name: str):
    """Extract a single material using Excel-provided data."""
    boverket = load_json(os.path.join(BASE_DIR, "Boverket.json"))
    opaque = load_json(os.path.join(BASE_DIR, "opaque_material.json"))

    if isinstance(boverket, dict):
        boverket_list = boverket.get("resources", boverket.get("Resources", []))
        if not boverket_list:
            boverket_list = list(boverket.values())
    elif isinstance(boverket, list):
        boverket_list = boverket
    else:
        raise ValueError("Unexpected Boverket.json structure")

    ec_data = find_by_resource_id(boverket_list, boverket_id)
    if ec_data is None:
        raise ValueError(f"No Boverket entry found with ID: {boverket_id}")

    mat_data = opaque.get(ep_id)
    if mat_data is None:
        raise ValueError(f"No opaque material entry found with ID: {ep_id}")

    ec = create_embodied_carbon(ec_data)
    return create_opaque_material(mat_data, ec, material_name)


def load_opaque_materials_from_excel(filename: str):
    """Load opaque materials from Excel database, skip incomplete rows, track failures."""
    path = os.path.join(PROJECT_ROOT, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Excel file not found: {path}")

    df = pd.read_excel(path, sheet_name="Opaque_Materials")

    # normalize column names: strip, lowercase, remove underscores
    df.columns = df.columns.str.strip()
    df.columns = df.columns.str.replace("_", " ")
    df.columns = df.columns.str.lower()

    # map the columns we care about
    column_map = {
        "material name": "material name",
        "boverket id": "boverket id",
        "energyplus identifier": "energyplus identifier"
    }

    # check that required columns exist
    if not all(col in df.columns for col in column_map.values()):
        raise ValueError(
            f"Excel sheet must contain columns: {list(column_map.keys())}. "
            f"Found: {list(df.columns)}"
        )

    materials = []
    skipped_materials = []

    for _, row in df.iterrows():
        material_name = str(row[column_map["material name"]])

        # Check for missing IDs
        boverket_id = row[column_map["boverket id"]]
        ep_id = row[column_map["energyplus identifier"]]

        if pd.isna(boverket_id) or pd.isna(ep_id):
            skipped_materials.append(material_name)
            continue

        try:
            material = extract_material(
                boverket_id=str(boverket_id),
                ep_id=str(ep_id),
                material_name=material_name
            )
            materials.append(material)
        except Exception as e:
            # If extraction fails (e.g., Boverket ID not found), skip and track
            print(f"Skipping '{material_name}' → {e}")
            skipped_materials.append(material_name)

    return materials, skipped_materials


def export_all_materials(materials):
    """Dump all material instances into a single JSON file."""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    today = datetime.today().strftime("%Y-%m-%d")
    output_file = os.path.join(
        OUTPUT_DIR, f"Extracted Materials_{today}.json"
    )

    all_data = {m.name: m.to_dict() for m in materials}

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=4)

    print(f"Exported all materials → {output_file}")


if __name__ == "__main__":
    materials, skipped = load_opaque_materials_from_excel("Material_Database.xlsx")
    export_all_materials(materials)

    total_processed = len(materials)
    total_skipped = len(skipped)

    print(f"\nSummary:")
    print(f"- Successfully processed materials: {total_processed}")
    print(f"- Skipped materials: {total_skipped}")

    if skipped:
        print("\nThe following materials could not be fulfilled:")
        for name in skipped:
            print(f"- {name}")


