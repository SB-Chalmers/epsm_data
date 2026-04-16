from epsm_data.infra.loaders.loader import (
    load_opaque_materials,
    load_layers,
    load_components,
    load_elements,
    load_buildings,
    load_window_elements,
)

from epsm_data.infra.exporters.json_exporter import export_all
# from epsm_data.infra.db.db_exporter import export_to_db

EXCEL_PATH = "data/Material_Database.xlsx"
JSON_PATH  = "data/opaque_material.json"
WINDOW_MATERIAL_JSON = "data/window_material.json"
WINDOW_CONSTRUCTION_JSON = "data/window_construction.json"

def run_export_outputs() -> None:
    """Load all domain objects and export to JSON and database."""
    materials = load_opaque_materials(EXCEL_PATH, JSON_PATH)
    opaque_lookup = {m.name: m for m in materials}

    layers = load_layers(EXCEL_PATH, opaque_lookup)
    layer_lookup = {l.layer_code: l for l in layers}

    components = load_components(EXCEL_PATH, layer_lookup)
    components_lookup = {c.name: c for c in components}

    elements = load_elements(EXCEL_PATH, components_lookup)
    elements_lookup = {e.name: e for e in elements}

    # fetch Boverket resources once and share with window loader
    from epsm_data.infra.api.boverket_client import fetch_material_resources
    resource_lookup = {str(r["ResourceId"]): r for r in fetch_material_resources()}

    window_elements = load_window_elements(
        EXCEL_PATH,
        WINDOW_MATERIAL_JSON,
        WINDOW_CONSTRUCTION_JSON,
        resource_lookup,
    )
    window_lookup = {w.name: w for w in window_elements}

    buildings = load_buildings(EXCEL_PATH, elements_lookup, window_lookup)

    export_all(materials, layers, components, elements, buildings, window_elements)
    #export_to_db(materials, layers, components, elements, buildings, window_elements)

if __name__ == "__main__":
    run_export_outputs()
    #python -m epsm_data.usecases.export_outputs