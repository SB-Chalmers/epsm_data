from InstanceLoader import (
    load_opaque_materials, load_layers,
    load_components, load_elements
)
from Exporter import export_all
# entry point

if __name__ == "__main__":
    opaque_materials = load_opaque_materials()
    opaque_lookup = {mat.name: mat for mat in opaque_materials}

    layers = load_layers(opaque_lookup)
    layer_lookup = {layer.layer_code: layer for layer in layers}

    components = load_components(layer_lookup)
    components_lookup = {comp.name: comp for comp in components}

    elements = load_elements(components_lookup)
    
    export_all(opaque_materials, layers, components, elements)