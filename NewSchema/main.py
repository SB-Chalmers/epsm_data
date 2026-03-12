from InstanceLoader import (
    load_opaque_materials, load_layers,
    load_components, load_elements, load_buildings
)

from Exporter import export_all
from DBExporter import export_to_db

from TabulaCheck import analyse_tabula_failures 

if __name__ == "__main__":
    opaque_materials = load_opaque_materials()
    
    opaque_lookup = {mat.name: mat for mat in opaque_materials}
    layers = load_layers(opaque_lookup)
    
    layer_lookup = {layer.layer_code: layer for layer in layers}
    components = load_components(layer_lookup)
    
    components_lookup = {comp.name: comp for comp in components}
    elements = load_elements(components_lookup)

    analyse_tabula_failures(elements)
    elements_lookup = {el.name: el for el in elements}
    buildings = load_buildings(elements_lookup)
    
    export_all(opaque_materials, layers, components, elements, buildings)
    export_to_db(opaque_materials, layers, components, elements, buildings) 