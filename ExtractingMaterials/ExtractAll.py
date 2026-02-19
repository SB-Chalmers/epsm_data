# python -m ExtractingMaterials.ExtractAll
import json
import os
from datetime import datetime
import pandas as pd
from EPSM_Enums import Roughness, ShearingLayer
from ClassDefinitions.Materials import OpaqueMaterial, Material
from ClassDefinitions.EmbodiedCarbon import EmbodiedCarbon
from ClassDefinitions.Layers import Layer
from ClassDefinitions.Components import Component

# Base directory of this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# JSON / Boverket helpers
def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def find_by_resource_id(boverket_list, resource_id):
    for item in boverket_list:
        if str(item.get("ResourceId")) == str(resource_id):
            return item
    return None

# Materials
def create_opaque_material(mat_data: dict, ec: EmbodiedCarbon, material_name: str) -> OpaqueMaterial:
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
        name=material_name,
        mat_type=mat_data.get("type", "EnergyMaterial"),
        embodied_carbon=ec,
        json_id=material_name,
        boverket_id=ec.resource_id
    )


def extract_material(boverket_id: str, ep_id: str, material_name: str):
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
    path = os.path.join(PROJECT_ROOT, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Excel file not found: {path}")

    df = pd.read_excel(path, sheet_name="Opaque_Materials")
    df.columns = df.columns.str.strip().str.lower().str.replace("_", " ")

    materials = []
    skipped_materials = []
    seen_materials = set()

    for _, row in df.iterrows():
        material_name = str(row["material name"])
        boverket_id = row["boverket id"]
        ep_id = row["energyplus identifier"]

        if material_name in seen_materials:
            skipped_materials.append((material_name, "Duplicate material name"))
            continue

        missing = []
        if pd.isna(boverket_id):
            missing.append("Boverket ID")
        if pd.isna(ep_id):
            missing.append("EnergyPlus Identifier")
        if missing:
            skipped_materials.append((material_name, f"Missing {', '.join(missing)}"))
            continue

        try:
            material = extract_material(str(boverket_id), str(ep_id), material_name)
            materials.append(material)
            seen_materials.add(material_name)
        except Exception as e:
            skipped_materials.append((material_name, str(e)))

    return materials, skipped_materials

# Layers
def load_layers_from_excel(filename: str, material_lookup: dict):
    df = pd.read_excel(filename, sheet_name="Layers")
    df.columns = df.columns.str.strip().str.lower().str.replace("_", " ")

    layers = []
    skipped_layers = []
    seen_layers = set()

    for _, row in df.iterrows():
        layer_code = row.get("layer code")
        layer_name = row.get("layer name") or layer_code
        archetype = row.get("archetype")

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
        for i in range(1, 4):
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

            materials_list.append((mat, frac)) ## instance instead of name, ALL of the instances as nested

        if not materials_list:
            skipped_layers.append((layer_code, "No valid materials found"))
            continue

        # Area fractions
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

        layer = Layer(
            thickness=thickness,
            materials=materials_list,
            name=layer_name,
            archetype = archetype
        )
        layer.layer_code = layer_code
        layers.append(layer)
        seen_layers.add(layer_code)

    return layers, skipped_layers

# Components
def load_components_from_excel(filename: str, layers_list: list):
    """
    Load components from Excel sheet "Components" using pre-loaded layers.
    Returns list of Component objects and skipped components with reasons.
    """

    path = os.path.join(PROJECT_ROOT, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Excel file not found: {path}")

    df = pd.read_excel(path, sheet_name="Components")
    df.columns = df.columns.str.strip().str.lower().str.replace("_", " ")

    layers_dict = {l.layer_code: l for l in layers_list}

    components = []
    skipped_components = []

    # Forward fill component codes
    if "component code" not in df.columns:
        raise ValueError("Components sheet must contain 'Component Code' column")
    df["component code"] = df["component code"].ffill()

    grouped = df.groupby("component code")
    for comp_code, group in grouped:
        layer_objs = []
        missing_layers = []

        for _, row in group.iterrows():
            layer_code = str(row.get("layers", "")).strip()
            layer_obj = layers_dict.get(layer_code)
            if layer_obj is None:
                missing_layers.append(layer_code)
                continue
            layer_objs.append(layer_obj)

        if not layer_objs:
            skipped_components.append((comp_code, f"No valid layers found: {missing_layers}"))
            continue
        
        archetype = group.iloc[0].get("archetype")

        # Determine shearing layer from first row
        shearing_layer_str = group.iloc[0].get("shearing layer")
        shearing_layer = next(
            (s for s in ShearingLayer if s.value.lower() == str(shearing_layer_str).strip().lower()),
            None  # Return None if not found
        )

        if shearing_layer is None:
            skipped_components.append((comp_code, f"Shearing Layer '{shearing_layer_str}' not found"))
            continue
        try:
            component = Component(
                name=comp_code,
                archetype= archetype,
                layers=layer_objs,
                shearing_layer=shearing_layer
            )
            components.append(component)
        except Exception as e:
            skipped_components.append((comp_code, str(e)))
            print(f"Skipping component '{comp_code}' → {e}")

    return components, skipped_components

# Export function
def export_materials_layers_components(
    materials,
    layers=None,
    components=None,
    export_materials=True,
    export_layers=True,
    export_components_flag=True,
    skipped_materials=None,
    skipped_layers=None,
    skipped_components=None
):
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    today = datetime.today().strftime("%Y-%m-%d")
    RED = "\033[91m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"

    # Store total warnings for final summary
    totals = {"materials": 0, "layers": 0, "components": 0}

    # Materials
    if export_materials:
        materials_file = os.path.join(OUTPUT_DIR, f"Materials_{today}.json")
        with open(materials_file, "w", encoding="utf-8") as f:
            json.dump({m.name: m.to_dict() for m in materials}, f, indent=4)
        print(f"\nExported materials: {materials_file}")
        print(f"Processed materials: {len(materials)}")

        # Warnings
        for m in materials:
            warnings = m.validate() if hasattr(m, "validate") else []
            totals["materials"] += len(warnings)
            for w in warnings:
                print(f"{YELLOW}[Material WARNING]{RESET} {m.name}: {w}")

        # Skipped
        if skipped_materials:
            print(f"Skipped materials: {len(skipped_materials)}")
            for name, reason in skipped_materials:
                print(f"{RED}[Material SKIPPED]{RESET} {name}: {reason}")

    # Layers
    if export_layers and layers:
        layers_file = os.path.join(OUTPUT_DIR, f"Layers_{today}.json")
        with open(layers_file, "w", encoding="utf-8") as f:
            json.dump({l.layer_code: l.to_dict() for l in layers}, f, indent=4)
        print(f"\nExported layers: {layers_file}")
        print(f"Processed layers: {len(layers)}")

        for l in layers:
            warnings = l.validate() if hasattr(l, "validate") else []
            totals["layers"] += len(warnings)
            for w in warnings:
                print(f"{YELLOW}[Layer WARNING]{RESET} {l.name}: {w}")

        if skipped_layers:
            print(f"Skipped layers: {len(skipped_layers)}")
            for name, reason in skipped_layers:
                print(f"{RED}[Layer SKIPPED]{RESET} {name}: {reason}")

    # Components
    if export_components_flag and components:
        components_file = os.path.join(OUTPUT_DIR, f"Components_{today}.json")
        with open(components_file, "w", encoding="utf-8") as f:
            json.dump({c.name: c.to_dict() for c in components}, f, indent=4)
        print(f"\nExported components: {components_file}")
        print(f"Processed components: {len(components)}")

        for c in components:
            warnings = c.validate() if hasattr(c, "validate") else []
            totals["components"] += len(warnings)
            for w in warnings:
                print(f"{YELLOW}[Component WARNING]{RESET} {c.name}: {w}")

        if skipped_components:
            print(f"Skipped components: {len(skipped_components)}")
            for name, reason in skipped_components:
                print(f"{RED}[Component SKIPPED]{RESET} {name}: {reason}")

    # Final summary
    print("\nFinal Summary (for exported JSONs):")
    if export_materials:
        print(f"Materials: Processed={len(materials)}, Skipped={len(skipped_materials)}, Warnings={totals['materials']}")
    if export_layers and layers:
        print(f"Layers: Processed={len(layers)}, Skipped={len(skipped_layers)}, Warnings={totals['layers']}")
    if export_components_flag and components:
        print(f"Components: Processed={len(components)}, Skipped={len(skipped_components)}, Warnings={totals['components']}")


if __name__ == "__main__":

    export_materials = True
    export_layers = True
    export_components_flag = True  # Adjust accordingly

    # Load materials
    materials, skipped_materials = [], []
    material_lookup = {}

    if export_materials or export_layers or export_components_flag:
        materials, skipped_materials = load_opaque_materials_from_excel("Material_Database.xlsx")
        material_lookup = {m.name: m for m in materials}

    # Load layers
    layers, skipped_layers = [], []
    if export_layers or export_components_flag:
        layers, skipped_layers = load_layers_from_excel("Material_Database.xlsx", material_lookup)

    # Load components
    components, skipped_components = [], []
    if export_components_flag:
        components, skipped_components = load_components_from_excel("Material_Database.xlsx", layers)

    # Export JSONs and produce warnings + final summary
    export_materials_layers_components(
        materials,
        layers,
        components,
        export_materials=export_materials,
        export_layers=export_layers,
        export_components_flag=export_components_flag,
        skipped_materials=skipped_materials,
        skipped_layers=skipped_layers,
        skipped_components=skipped_components
    )



