# python -m ExtractingMaterials.ExtractLayers
import json
import os
from datetime import datetime
import pandas as pd
from EPSM_Enums import Roughness
from ClassDefinitions.Materials import OpaqueMaterial, Material
from ClassDefinitions.EmbodiedCarbon import EmbodiedCarbon
from ClassDefinitions.Layers import Layer

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


def create_opaque_material(mat_data: dict, ec: EmbodiedCarbon, material_name: str) -> OpaqueMaterial:
    """Instantiate OpaqueMaterial and override name from Excel."""
    try:
        roughness_enum = next(r for r in Roughness if r.value == mat_data["roughness"])
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
        name=material_name,  # Override name from Excel
        mat_type=mat_data.get("type", "EnergyMaterial"),
        embodied_carbon=ec,
        json_id=material_name,
        boverket_id=ec.resource_id
    )


def extract_material(boverket_id: str, ep_id: str, material_name: str):
    """Extract a single material using Excel-provided data."""
    boverket = load_json(os.path.join(BASE_DIR, "Boverket.json"))
    opaque = load_json(os.path.join(BASE_DIR, "opaque_material.json"))

    # Prepare Boverket list
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

    ec = EmbodiedCarbon.from_boverket(ec_data)
    return create_opaque_material(mat_data, ec, material_name)


def load_opaque_materials_from_excel(filename: str):
    """Load opaque materials from Excel database, skip incomplete rows or duplicates."""
    path = os.path.join(PROJECT_ROOT, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Excel file not found: {path}")

    df = pd.read_excel(path, sheet_name="Opaque_Materials")
    df.columns = df.columns.str.strip().str.lower().str.replace("_", " ")

    # Map required columns
    column_map = {
        "material name": "material name",
        "boverket id": "boverket id",
        "energyplus identifier": "energyplus identifier"
    }
    if not all(col in df.columns for col in column_map.values()):
        raise ValueError(f"Excel sheet must contain columns: {list(column_map.keys())}. Found: {list(df.columns)}")

    materials = []
    skipped_materials = []
    seen_materials = set()

    for _, row in df.iterrows():
        material_name = str(row[column_map["material name"]])
        boverket_id = row[column_map["boverket id"]]
        ep_id = row[column_map["energyplus identifier"]]

        # Check for Duplicate
        if material_name in seen_materials:
            skipped_materials.append((material_name, "Duplicate material name"))
            continue

        # Specific checks for missing IDs
        missing = []
        if pd.isna(boverket_id):
            missing.append("Boverket ID")
        if pd.isna(ep_id):
            missing.append("EnergyPlus Identifier")
        
        if missing:
            reason = f"Missing {', '.join(missing)}"
            skipped_materials.append((material_name, reason))
            continue

        try:
            material = extract_material(str(boverket_id), str(ep_id), material_name)
            materials.append(material)
            seen_materials.add(material_name)
        except Exception as e:
            skipped_materials.append((material_name, str(e)))
            print(f"Skipping '{material_name}' → {e}")

    return materials, skipped_materials


def load_layers_from_excel(filename: str, material_lookup: dict):
    """
    Load layers from Excel sheet "Layers" and map materials from material_lookup.
    Returns list of Layer objects and skipped layers with reasons.

    Area fraction rules:
    - Single-material layer: missing fraction → 1.0
    - Composite layer:
        * keep given fractions
        * split remaining fraction evenly across missing ones
        * skip if fractions exceed 1 or final sum != 1
    """
    df = pd.read_excel(filename, sheet_name="Layers")
    df.columns = df.columns.str.strip().str.lower().str.replace("_", " ")

    layers = []
    skipped_layers = []
    seen_layers = set()

    for _, row in df.iterrows():
        layer_code = row.get("layer code")
        layer_name = row.get("layer name")  # Used inside JSON

        if pd.isna(layer_code) or str(layer_code).strip() == "":
            skipped_layers.append(("Unnamed layer", "Missing layer code"))
            continue

        layer_code = str(layer_code).strip()
        layer_name = str(layer_name).strip() if not pd.isna(layer_name) else layer_code

        if layer_code in seen_layers:
            skipped_layers.append((layer_code, "Duplicate layer code"))
            continue

        # Thickness
        try:
            thickness = float(str(row["layer thickness"]).replace(",", "."))
        except Exception:
            skipped_layers.append((layer_code, "Invalid thickness"))
            continue

        # Collect materials
        materials_list = []
        for i in range(1, 4):  # up to 3 materials
            mat_name = row.get(f"material {i}")
            if pd.isna(mat_name) or mat_name == "":
                continue

            mat = material_lookup.get(mat_name)
            if mat is None:
                skipped_layers.append((layer_code, f"Material '{mat_name}' not found"))
                continue

            frac = row.get(f"material {i} area ratio")
            if pd.isna(frac):
                frac = None
            else:
                try:
                    frac = float(str(frac).replace(",", "."))
                except Exception:
                    frac = None

            materials_list.append((mat, frac))

        if not materials_list:
            skipped_layers.append((layer_code, "No valid materials found"))
            continue

        # --- Area fraction handling ---
        if len(materials_list) == 1:
            mat, frac = materials_list[0]
            materials_list[0] = (mat, 1.0 if frac is None else frac)
        else:
            fractions = [f for _, f in materials_list]
            known_sum = sum(f for f in fractions if f is not None)
            missing_idx = [i for i, f in enumerate(fractions) if f is None]

            if known_sum > 1.0:
                skipped_layers.append((layer_code, "Area fractions exceed 1"))
                continue

            if missing_idx:
                remaining = 1.0 - known_sum
                split = remaining / len(missing_idx)
                for idx in missing_idx:
                    mat, _ = materials_list[idx]
                    materials_list[idx] = (mat, split)

            final_sum = sum(f for _, f in materials_list)
            if round(final_sum, 6) != 1.0:
                skipped_layers.append((layer_code, "Area fractions do not sum to 1"))
                continue

        # Append the Layer object
        layer = Layer(
            thickness=thickness,
            materials=materials_list,
            layer_name=layer_name
        )
        layer.layer_code = layer_code
        layers.append(layer)
        seen_layers.add(layer_code)

    return layers, skipped_layers

def export_materials_and_layers_separately(
    materials, layers=None, export_materials=True, export_layers=True,
    skipped_materials=None, skipped_layers=None
):
    """Export materials and layers into separate JSON files."""
    
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    today = datetime.today().strftime("%Y-%m-%d")

    # Export materials
    if export_materials:
        materials_file = os.path.join(OUTPUT_DIR, f"Materials_{today}.json")
        materials_data = {m.name: m.to_dict() for m in materials}
        with open(materials_file, "w", encoding="utf-8") as f:
            json.dump(materials_data, f, indent=4)
        print(f"Exported materials: {materials_file}")

        print(f"\nSuccessfully processed materials: {len(materials)}")
        if skipped_materials:
            print(f"\nSkipped materials: {len(skipped_materials)}")
            for name, reason in skipped_materials:
                print(f"- {name}: {reason}")

    # Export layers
    if export_layers and layers:
        layers_file = os.path.join(OUTPUT_DIR, f"Layers_{today}.json")
        layers_data = {l.layer_code: l.to_dict() for l in layers}
        with open(layers_file, "w", encoding="utf-8") as f:
            json.dump(layers_data, f, indent=4)
        print(f"\nExported layers: {layers_file}")

        print(f"\nSuccessfully processed layers: {len(layers)}")
        if skipped_layers:
            print(f"\nSkipped layers: {len(skipped_layers)}")
            for name, reason in skipped_layers:
                print(f"- {name}: {reason}")


if __name__ == "__main__":
    materials, skipped_materials = load_opaque_materials_from_excel("Material_Database.xlsx")
    material_lookup = {m.name: m for m in materials}

    layers, skipped_layers = load_layers_from_excel("Material_Database.xlsx", material_lookup)

    export_materials_only = False
    export_layers_only = True # Adjust accordingly

    export_materials_and_layers_separately(
        materials,
        layers,
        export_materials=export_materials_only,
        export_layers=export_layers_only,
        skipped_materials=skipped_materials,
        skipped_layers=skipped_layers
    )

    #Check if any property/value is missing in any instance (report)
    