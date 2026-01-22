# python -m ExtractingMaterials.Extract
import json
import os
from datetime import datetime
from EPSM_Enums import EmbodiedCarbon, Roughness
from ClassDefinitions.Materials import OpaqueMaterial

# Base directory of this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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
    except:
        tsl = 50

    return EmbodiedCarbon(
        product_name=data.get("Name", "Unknown"),
        resource_id=str(data.get("ResourceId")),
        A1_A3_conservative=get_value("A1-A3 Conservative"),
        A4=get_value("A4"),
        A5_conservative=get_value("A5.1"),
        A1_A3_typical=get_value("A1-A3 Typical"),
        A1_A3_factor_conservative=float(data.get("ConservativeDataConversionFactor", 1)),
        A5_factor_byggspill=float(data.get("WasteFactor", 1)),
        conversion_factor=float(data.get("Conversions", [{}])[0].get("Value", 1)),
        technical_service_life=tsl
    )


def create_opaque_material(mat_data: dict, ec: EmbodiedCarbon) -> OpaqueMaterial:
    """Instantiate OpaqueMaterial from material JSON + EmbodiedCarbon instance."""
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
        name=mat_data["identifier"],
        mat_type=mat_data.get("type", "EnergyMaterial"),
        embodied_carbon=ec,
        json_id=mat_data["identifier"],
        boverket_id=ec.resource_id
    )


def extract_material_pair(boverket_id: str, material_id: str):
    """Given two IDs, generate a material instance."""
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

    mat_data = opaque.get(material_id)
    if mat_data is None:
        raise ValueError(f"No opaque material entry found with ID: {material_id}")

    ec = create_embodied_carbon(ec_data)
    material = create_opaque_material(mat_data, ec)
    return material


def export_all_materials(materials):
    """Dump all material instances into a single JSON file with the date in filename."""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    today = datetime.today().strftime("%Y-%m-%d")
    output_file = os.path.join(OUTPUT_DIR, f"Extracted Materials_{today}.json")

    all_data = {m.name: m.to_dict() for m in materials}

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=4)

    print(f"Exported all materials → {output_file}")


if __name__ == "__main__":
    pairs = [
        ("6000000078", "1/2IN Gypsum"),
        ("6000000154", "100mm Normalweight concrete floor"),
        ("6000000003", "I01 25mm insulation board") # These pairs are just examples for now

    ]

    all_materials = []
    for boverket_id, mat_id in pairs:
        material = extract_material_pair(boverket_id, mat_id)
        all_materials.append(material)

    export_all_materials(all_materials)

    # The excel extraction needs to be added
    # Some deebugging as well, and debugg leftovers
    # Name should be grabbed from excel (for now it's from honeybee)
    # Translucent materials?
